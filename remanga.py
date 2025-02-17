import os
import re
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import mimetypes

# Selenium setup
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    driver_service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=driver_service, options=chrome_options)
    return driver

# Function to split large images
def split_image(image_path, output_folder, chapter_index, start_page_index, piece_height=2000):
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        print(f"Original image size: {img_width}x{img_height}")

        current_page_index = start_page_index
        img_format = img.format.lower()  # Get original format (e.g., 'jpeg', 'png', 'webp')

        if img_height <= piece_height:
            output_filename = f"chapter{chapter_index}_{current_page_index:02}.{img_format}"
            output_path = os.path.join(output_folder, output_filename)
            img.save(output_path, format=img_format.upper(), quality=100)
            print(f"Saved: {output_path}")
            current_page_index += 1
        else:
            num_pieces = img_height // piece_height
            for cut_number in range(num_pieces):
                left, upper, right, lower = 0, cut_number * piece_height, img_width, (cut_number + 1) * piece_height
                piece = img.crop((left, upper, right, lower))
                output_filename = f"chapter{chapter_index}_{current_page_index:02}.{img_format}"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, format=img_format.upper(), quality=100)
                print(f"Saved: {output_path}")
                current_page_index += 1

            remainder = img_height % piece_height
            if remainder > 0:
                box = (0, img_height - remainder, img_width, img_height)
                piece = img.crop(box)
                output_filename = f"chapter{chapter_index}_{current_page_index:02}.{img_format}"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, format=img_format.upper(), quality=100)
                print(f"Saved: {output_path}")
                current_page_index += 1

        return current_page_index

def scrape_chapters(driver, manga_url):
    print(f"Scraping chapters from {manga_url}")
    driver.get(manga_url)

    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.Chapters_container__5S4y_"))
        )
    except Exception as e:
        print(f"Failed to load chapters: {e}")
        return []

    chapters = []
    chapter_elements = driver.find_elements(By.CSS_SELECTOR, "div.Chapters_container__5S4y_ a.Chapters_chapterItem__4Wz_G")
    for chapter_element in chapter_elements:
        href = chapter_element.get_attribute("href")
        chapter_text = chapter_element.find_element(By.CSS_SELECTOR, "span.Chapters_tome__tBNYU").text
        chapter_number = re.search(r"\d+", chapter_text)
        if chapter_number:
            # Check if the href already has the full URL
            if href.startswith("https://"):
                chapters.append((int(chapter_number.group()), href))
            else:
                # If href is a relative URL, prepend the base URL
                chapters.append((int(chapter_number.group()), f"https://remanga.org{href}"))

    chapters.sort(key=lambda x: x[0])
    print(f"Found {len(chapters)} chapters.")
    return chapters

# Download images for a chapter and handle lazy-loading
def download_images_for_chapter(driver, chapter_url, manga_title, chapter_index):
    print(f"Processing Chapter {chapter_index}: {chapter_url}")
    driver.get(chapter_url)

    # Function to wait for and handle lazy loading of images
    def scroll_to_load_images():
        SCROLL_PAUSE_TIME = 2  # Pause to allow images to load
        last_height = driver.execute_script("return document.body.scrollHeight")
        print(f"Initial page height: {last_height}")

        while True:
            # Scroll to the bottom of the page
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)

            # Check for new height
            new_height = driver.execute_script("return document.body.scrollHeight")
            print(f"New page height: {new_height}")
            if new_height == last_height:
                break  # Exit if no new content is loaded
            last_height = new_height

    # Execute scrolling to load all images for the current chapter
    scroll_to_load_images()

    # Find the images for the current chapter
    image_elements = driver.find_elements(By.CSS_SELECTOR, "img#chapter-image")
    
    # Log how many images are found
    print(f"Found {len(image_elements)} images for Chapter {chapter_index}")

    # Ensure that we have found images for the current chapter
    if not image_elements:
        print(f"No images found for Chapter {chapter_index}")
        return

    # Create the folder for the chapter
    folder_name = os.path.join(manga_title.lower().replace(" ", "_"), f"chapter_{chapter_index}")
    os.makedirs(folder_name, exist_ok=True)

    current_page_index = 1

    # Loop through each image and download it
    for idx, img_element in enumerate(image_elements):
        # Ensure the image belongs to the current chapter
        img_url = img_element.get_attribute("src")
        chapter_url_from_img = img_element.find_element(By.XPATH, "..").get_attribute("href")
        
        # Skip images from other chapters based on href change
        if chapter_url_from_img != chapter_url:
            continue

        # Debug: Print the img_url to verify if it’s correct
        print(f"Downloading image from: {img_url}")

        # Verify the image URL is valid
        if img_url and img_url.startswith("https"):
            try:
                # Add headers to the request to bypass 403 restrictions
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
                    ),
                    "Referer": chapter_url,
                }

                # Fetch the image data with headers
                response = requests.get(img_url, headers=headers, timeout=10)

                # Debug: Check the response status code
                print(f"Image URL: {img_url}, Status Code: {response.status_code}")

                # Check for successful response
                if response.status_code == 200:
                    # Determine the original format based on Content-Type
                    content_type = response.headers.get("Content-Type", "")
                    ext = mimetypes.guess_extension(content_type) or ".jpg"  # Default to .jpg if uncertain

                    temp_image_path = os.path.join(folder_name, f"temp_page_{idx + 1}{ext}")

                    # Save the original image in its native format
                    with open(temp_image_path, "wb") as img_file:
                        img_file.write(response.content)
                    print(f"Downloaded: {temp_image_path}")

                    # Split the image if necessary
                    current_page_index = split_image(
                        temp_image_path,
                        folder_name,
                        manga_title,
                        chapter_index,
                        current_page_index,
                        piece_height=2000
                    )

                    # Remove the temporary file after processing
                    os.remove(temp_image_path)
                else:
                    print(f"Failed to download image {img_url}, Status Code: {response.status_code}")
            except Exception as e:
                print(f"Error downloading or processing image {img_url}: {e}")
        else:
            print(f"Invalid image URL: {img_url}")

# Main function
def main():
    manga_url = "https://remanga.org/manga/on-the-way-to-see-mom?p=chapters"
    manga_title = "On the Way to See Mom"
    driver = setup_driver()
    try:
        # Scrape chapters from the manga URL
        chapters = scrape_chapters(driver, manga_url)

        # Reverse the order of the chapters (latest first)
        chapters.reverse()

        # Process chapters in reversed order
        for chapter_index, (chapter_number, chapter_url) in enumerate(chapters, start=1):
            download_images_for_chapter(driver, chapter_url, manga_title, chapter_index)
    finally:
        driver.quit()

    print("Download completed!")

if __name__ == "__main__":
    main()