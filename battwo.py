import os
import re
import time
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By  
from selenium.webdriver.common.action_chains import ActionChains

# Selenium setup
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--start-maximized")
    
    # Use ChromeDriverManager().install() to handle the chromedriver without explicitly setting path
    driver_service = Service(ChromeDriverManager().install())  # Set up the ChromeDriver service
    driver = webdriver.Chrome(service=driver_service, options=chrome_options)  # Pass the driver service correctly
    return driver

# Function to split large images
def split_image(image_path, output_folder, manga_title, chapter_index, start_page_index, piece_height=2000):
    manga_title = manga_title.lower().replace(" ", "_")
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        print(f"Original image size: {img_width}x{img_height}")

        current_page_index = start_page_index

        if img_height <= piece_height:
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")

            output_filename = f"chapter{chapter_index}_{current_page_index:02}.jpg"
            output_path = os.path.join(output_folder, output_filename)
            img.save(output_path, "JPEG")
            print(f"Saved: {output_path}")
            current_page_index += 1
        else:
            num_pieces = img_height // piece_height
            for cut_number in range(num_pieces):
                left, upper, right, lower = 0, cut_number * piece_height, img_width, (cut_number + 1) * piece_height
                piece = img.crop((left, upper, right, lower))

                if piece.mode in ["RGBA", "P"]:
                    piece = piece.convert("RGB")

                output_filename = f"chapter{chapter_index}_{current_page_index:02}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                print(f"Saved: {output_path}")
                current_page_index += 1

            remainder = img_height % piece_height
            if remainder > 0:
                box = (0, img_height - remainder, img_width, img_height)
                piece = img.crop(box)

                if piece.mode in ["RGBA", "P"]:
                    piece = piece.convert("RGB")

                output_filename = f"chapter{chapter_index}_{current_page_index:02}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                print(f"Saved: {output_path}")
                current_page_index += 1

        return current_page_index

# Download images for a chapter based on the provided HTML structure
# Function to download images for a chapter
def download_images_for_chapter(driver, chapter_url, manga_title, chapter_index):
    print(f"Processing Chapter {chapter_index}: {chapter_url}")
    driver.get(chapter_url)

    # Wait for the image elements to load
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[name='image-items'] img"))
        )
    except Exception as e:
        print(f"Images not found for Chapter {chapter_index}: {e}")
        return

    image_elements = driver.find_elements(By.CSS_SELECTOR, "div[name='image-items'] img")
    if not image_elements:
        print(f"No images found for Chapter {chapter_index}")
        return

    folder_name = os.path.join(manga_title.lower().replace(" ", "_"), f"chapter_{chapter_index}")
    os.makedirs(folder_name, exist_ok=True)

    current_page_index = 1
    for idx, img in enumerate(image_elements):
        img_url = img.get_attribute("src")

        # Ensure we get the full image URL
        if img_url and img_url.startswith("https"):
            try:
                img_data = requests.get(img_url, timeout=10).content
                temp_image_path = os.path.join(folder_name, f"temp_page_{idx + 1}.jpg")

                # Save the image temporarily
                with open(temp_image_path, "wb") as img_file:
                    img_file.write(img_data)
                print(f"Downloaded: {temp_image_path}")

                # Split the image if necessary
                current_page_index = split_image(
                    temp_image_path, folder_name, manga_title, chapter_index, current_page_index
                )

                # Remove the temporary file
                os.remove(temp_image_path)
            except Exception as e:
                print(f"Error downloading image {img_url}: {e}")



# Scrape chapters from the main page
def scrape_chapters(driver, manga_url):
    print(f"Scraping chapters from {manga_url}")
    driver.get(manga_url)

    # Wait for the chapter list div to be visible
    try:
        # Wait for the chapter list container to load (adjust timeout if necessary)
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[name="chapter-list"]'))
        )
    except Exception as e:
        print(f"Failed to load content: {e}")
        return []

    # Locate the chapter list
    try:
        chapter_list = driver.find_element(By.CSS_SELECTOR, 'div[name="chapter-list"]')
        chapter_links = chapter_list.find_elements(By.CSS_SELECTOR, 'a.link-hover')  # Targeting the chapter links
    except Exception as e:
        print(f"Failed to locate chapter list: {e}")
        return []

    # Extract chapter details
    chapters = []
    for link in chapter_links:
        href = link.get_attribute("href")
        chapter_number_match = re.search(r"ch_(\d+)", href)  # Extracting chapter number from URL
        if chapter_number_match:
            chapter_number = int(chapter_number_match.group(1))
            chapters.append((chapter_number, href + "?load=2"))  # Appending ?load=2

    chapters.sort(key=lambda x: x[0])  # Sort chapters numerically
    print(f"Found {len(chapters)} chapters.")
    return chapters

# Main function
def main():
    manga_url = "https://battwo.com/title/181053-muse-on-fame-official"
    manga_title = "Muse on Fame"

    driver = setup_driver()

    try:
        chapters = scrape_chapters(driver, manga_url)
        for chapter_number, chapter_url in chapters[0:]:

            download_images_for_chapter(driver, chapter_url, manga_title, chapter_number)
    finally:
        driver.quit()

    print("Download completed!")

# Run the script
if __name__ == "__main__":
    main()