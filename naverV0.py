import os
import requests
import time
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

from requests.exceptions import RequestException
from PIL import UnidentifiedImageError

# Function to download images for a specific chapter
def download_images_for_chapter(chapter_number, chapter_url, manga_url):
    manga_title = extract_manga_title(manga_url)
    print(f"Processing Chapter {chapter_number} at {chapter_url}")

    try:
        response = requests.get(chapter_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        # Find images
        image_tags = soup.find_all("img", alt="comic content")
        if not image_tags:
            print(f"No images found for Chapter {chapter_number}.")
            return

        print(f"Found {len(image_tags)} images in Chapter {chapter_number}")
        folder_name = f"{manga_title}/chapter_{chapter_number}"
        os.makedirs(folder_name, exist_ok=True)

        current_page_index = 1
        for idx, img_tag in enumerate(image_tags):
            img_url = img_tag.get("data-src") or img_tag.get("src")
            print(f"img_url: {img_url}")
            if img_url and "thumbnail" not in img_url:  # Skip thumbnails by checking the URL
                # img_url = img_url.strip().lower()

                try:
                    # Add User-Agent header to simulate a real browser request
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
                    }

                    img_data = requests.get(img_url)
                    # Save image as temporary file
                    img_path = os.path.join(folder_name, f"temp_page_{idx + 1}.jpg")
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)

                    current_page_index = split_image(img_path, folder_name, manga_title, chapter_number, current_page_index)
                    os.remove(img_path)

                except RequestException as e:
                    print(f"Error downloading page {idx + 1} at {img_url}: {e}")
                except Exception as e:
                    print(f"Unexpected error: {e}")
    except Exception as e:
        print(f"Error processing Chapter {chapter_number}: {e}")
# Extract manga title from URL
def extract_manga_title(manga_url):
    manga_title = manga_url.split("/titleId=")[-1]
    return manga_title.replace("-", " ").title()

# Split large images into smaller pieces
def split_image(image_path, output_folder, manga_title, chapter_number, start_page_index, piece_height=1600):
    manga_title = manga_title.lower().replace(" ", "_")
    with Image.open(image_path) as img:
        img_width, img_height = img.size

        current_page_index = start_page_index
        if img_height <= piece_height:
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")

            output_filename = f"{manga_title}-chapter{chapter_number}-{current_page_index}.jpg"
            output_path = os.path.join(output_folder, output_filename)
            img.save(output_path, "JPEG")
            current_page_index += 1
        else:
            num_pieces = img_height // piece_height
            for cut_number in range(num_pieces):
                box = (0, cut_number * piece_height, img_width, (cut_number + 1) * piece_height)
                piece = img.crop(box)
                if piece.mode in ["RGBA", "P"]:
                    piece = piece.convert("RGB")

                output_filename = f"{manga_title}-chapter{chapter_number}-{current_page_index}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                current_page_index += 1

            remainder = img_height % piece_height
            if remainder > 0:
                box = (0, img_height - remainder, img_width, img_height)
                piece = img.crop(box)
                if piece.mode in ["RGBA", "P"]:
                    piece = piece.convert("RGB")

                output_filename = f"{manga_title}-chapter{chapter_number}-{current_page_index}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                current_page_index += 1

        return current_page_index

# Scrape chapters from the manga list page
def scrape_chapters_with_selenium(manga_url):
    # Set up Selenium WebDriver with WebDriverManager
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.options import Options
    import time

    # Set up the WebDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Load the page
        driver.get(manga_url)
        time.sleep(3)  # Wait for JavaScript to load the page

        # Get the page source after JavaScript execution
        page_source = driver.page_source

        # Parse with BeautifulSoup
        soup = BeautifulSoup(page_source, "html.parser")

        # Find all chapter list items
        chapter_list_items = soup.find_all("li", class_="EpisodeListList__item--M8zq4")
        chapters = []
        base_url = "https://comic.naver.com"

        for li in chapter_list_items:
            link = li.find("a", href=True)
            if link:
                href = link.get("href")
                full_url = f"{base_url}{href}"
                chapters.append(full_url)

        print(f"Found {len(chapters)} chapters.")
        return chapters

    except Exception as e:
        print(f"Error occurred: {e}")
        return []

    finally:
        driver.quit()  # Close the browser

# Main function
def main():
    manga_url = "https://comic.naver.com/webtoon/list?titleId=814753"
    chapters = scrape_chapters_with_selenium(manga_url)

    for chapter_number, chapter_href in enumerate(chapters, start=1):  # Enumerate to generate chapter numbers
        download_images_for_chapter(chapter_number, chapter_href, manga_url)

    print("Download completed!")

if __name__ == "__main__":
    main()