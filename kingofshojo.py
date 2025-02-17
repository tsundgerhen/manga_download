import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from PIL import Image
import re
import time

# Function to set up the Selenium WebDriver
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
    driver = webdriver.Chrome(options=chrome_options)  # Make sure to have the correct path to ChromeDriver
    return driver

# Function to download images for a specific chapter using Selenium
def download_images_for_chapter(chapter_number, chapter_url, manga_title):
    print(f"Processing Chapter {chapter_number}: {chapter_url}")
    
    try:
        driver = setup_driver()
        driver.get(chapter_url)

        # Wait for the page to fully load (increase time if necessary)
        time.sleep(5)  # Adjust sleep time based on page loading speed

        # Retrieve the page source after it's fully loaded
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
    except Exception as e:
        print(f"Failed to fetch chapter page: {e}")
        return

    # Find the div with id 'readerarea' and class 'rdminimal'
    reader_area_div = soup.find("div", id="readerarea", class_="rdminimal")
    if not reader_area_div:
        print(f"Reader area not found for Chapter {chapter_number}.")
        return

    img_tags = reader_area_div.find_all("img", src=True)
    valid_imgs = []

    for img in img_tags:
        img_alt = img.get("alt", "")
        img_title = img.get("title", "")
        img_src = img.get("src", "")

        # Check if the chapter number is in the title or alt text (more flexible match)
        if str(chapter_number) in img_title or str(chapter_number) in img_alt:
            if "wp-content/uploads" in img_src:
                valid_imgs.append(img_src)

    if not valid_imgs:
        print(f"No valid images found for Chapter {chapter_number}.")
        return

    print(f"Found {len(valid_imgs)} images in Chapter {chapter_number}")

    folder_name = os.path.join(manga_title.lower().replace(" ", "_"), f"chapter_{chapter_number}")
    os.makedirs(folder_name, exist_ok=True)

    current_page_index = 1  # Start the page index for this chapter
    for idx, img_url in enumerate(valid_imgs):
        try:
            img_data = requests.get(img_url, timeout=10).content
            temp_image_path = os.path.join(folder_name, f"temp_page_{idx + 1}.jpg")

            # Save the image temporarily
            with open(temp_image_path, "wb") as img_file:
                img_file.write(img_data)
            print(f"Downloaded: {temp_image_path}")

            # Split the image into pieces if necessary
            current_page_index = split_image(
                temp_image_path, folder_name, manga_title, chapter_number, current_page_index
            )

            # Remove the temporary file
            os.remove(temp_image_path)

        except Exception as e:
            print(f"Error downloading image {img_url}: {e}")

# Function to split an image into smaller pieces
def split_image(image_path, output_folder, manga_title, chapter_number, start_page_index, piece_height=2000):
    manga_title = manga_title.lower().replace(" ", "_")
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        print(f"Original image size: {img_width}x{img_height}")

        current_page_index = start_page_index

        if img_height <= piece_height:
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")

            output_filename = f"{manga_title}_chapter{chapter_number}_{current_page_index:02}.jpg"
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

                output_filename = f"{manga_title}_chapter{chapter_number}_{current_page_index:02}.jpg"
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

                output_filename = f"{manga_title}_chapter{chapter_number}_{current_page_index:02}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                print(f"Saved: {output_path}")
                current_page_index += 1

        return current_page_index

# Function to scrape chapters from the chapter list
def scrape_chapters(manga_url):
    print(f"Scraping chapters from {manga_url}")
    
    try:
        response = requests.get(manga_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Failed to fetch manga page: {e}")
        return []

    chapter_list_div = soup.find("div", class_="eplister", id="chapterlist")
    if not chapter_list_div:
        print("Chapter list not found.")
        return []

    chapter_links = chapter_list_div.find_all("a", href=True)
    chapters = []
    for link in chapter_links:
        href = link.get("href")
        if href:
            chapter_number_match = re.search(r"Chapter (\d+)", link.text.strip())
            if chapter_number_match:
                chapter_number = int(chapter_number_match.group(1))
                chapters.append((chapter_number, href))

    chapters.sort(key=lambda x: x[0])  # Sort chapters numerically
    print(f"Found {len(chapters)} chapters.")
    return chapters

# Main function
def main():
    manga_url = "https://kingofshojo.com/manga/seduce-the-villains-father/"
    manga_title = "Seduce the Villain’s Father"  # Set manga title

    chapters = scrape_chapters(manga_url)
    start_index = 81  # Start from chapter 2 81 === 76 
    end_index = 165    # End at chapter 5 

    # Assuming chapters is a list of tuples with chapter_number and chapter_url
    for chapter_number, chapter_url in chapters[start_index - 1:end_index]:
        download_images_for_chapter(chapter_number, chapter_url, manga_title)

    print("Download completed!")

# Run the script
if __name__ == "__main__":
    main()