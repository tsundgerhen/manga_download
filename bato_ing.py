import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
from urllib.parse import urljoin
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

# Function to fetch page with Selenium (JavaScript rendered)
def fetch_page_with_selenium(chapter_url):
    options = Options()
    options.headless = True  # Run in headless mode (no UI)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(chapter_url)
    time.sleep(5)  # Wait for JavaScript to load
    page_source = driver.page_source
    driver.quit()
    return page_source

# Function to download images for a specific chapter and split large images
def download_images_for_chapter(chapter_number, chapter_url, manga_url):
    manga_title = extract_manga_title(manga_url)  # Get the manga title
    print(f"Processing Chapter {chapter_number} at {chapter_url}")

    page_source = fetch_page_with_selenium(chapter_url)
    soup = BeautifulSoup(page_source, "html.parser")

    image_divs = soup.find_all("div", {"data-name": "image-item"})
    if not image_divs:
        print(f"No images found for Chapter {chapter_number}.")
        return

    print(f"Found {len(image_divs)} images in Chapter {chapter_number}")

    folder_name = os.path.join(manga_title, f"chapter_{chapter_number}")
    os.makedirs(folder_name, exist_ok=True)

    current_page_index = 1

    for idx, image_div in enumerate(image_divs):
        img_tag = image_div.find("img")
        if img_tag and img_tag.get("src"):
            img_url = img_tag["src"]
            try:
                img_data = requests.get(img_url).content
                img_path = os.path.join(folder_name, f"temp_page_{idx + 1}.jpg")
                with open(img_path, "wb") as img_file:
                    img_file.write(img_data)
                print(f"Downloaded page {idx + 1} for Chapter {chapter_number}")

                current_page_index = split_image(img_path, folder_name, manga_title, chapter_number, current_page_index)
                os.remove(img_path)  # Remove temporary image
            except Exception as e:
                print(f"Error downloading page {idx + 1}: {e}")
        else:
            print(f"No image found in div {idx + 1}. Skipping.")

# Function to extract manga title from manga URL
def extract_manga_title(manga_url):
    manga_title = manga_url.split("/")[-1]
    manga_title = re.sub(r"[<>:\"/\\|?*]", "", manga_title)  # Remove invalid characters
    return manga_title

# Function to split large images
def split_image(image_path, output_folder, manga_title, chapter_number, start_page_index, piece_height=2000):
    manga_title = manga_title.lower().replace(" ", "_")

    with Image.open(image_path) as img:
        img_width, img_height = img.size
        print(f"Original image size: {img_width}x{img_height}")

        current_page_index = start_page_index

        if img_height <= piece_height:
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")

            output_filename = f"{manga_title}_chapter{chapter_number}_{current_page_index}.jpg"
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

                output_filename = f"{manga_title}_chapter{chapter_number}_{current_page_index}.jpg"
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

                output_filename = f"{manga_title}_chapter{chapter_number}_{current_page_index}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                print(f"Saved: {output_path}")
                current_page_index += 1

        return current_page_index

# Function to scrape chapter list
def scrape_chapters(manga_url):
    print(f"Scraping chapters for {manga_url}")

    page_source = fetch_page_with_selenium(manga_url)
    soup = BeautifulSoup(page_source, "html.parser")

    chapter_list_div = soup.find("div", class_="group flex flex-col")
    if not chapter_list_div:
        print("Could not find the chapter list div.")
        return []

    chapter_links = chapter_list_div.find_all("a", href=True)
    chapters = []
    for link in chapter_links:
        href = link.get("href")
        if href and "ch_" in href:
            match = re.search(r"ch_(\d+)", href)
            if match:
                chapter_number = int(match.group(1))
                full_url = urljoin(manga_url, href)
                chapters.append((chapter_number, full_url))

    chapters.sort(key=lambda x: x[0])
    print(f"Found {len(chapters)} chapters.")
    return chapters

# Main function
def main():
    manga_url = "https://bato.ing/title/84772-olgami"
    chapters = scrape_chapters(manga_url)

    for chapter_number, chapter_href in chapters:
        download_images_for_chapter(chapter_number, chapter_href, manga_url)

    print("Download completed!")

if __name__ == "__main__":
    main()