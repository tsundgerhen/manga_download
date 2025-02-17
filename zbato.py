import os
import re
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


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


# Split large images
from PIL import ImageSequence

def split_image(image_path, output_folder, manga_title, chapter_index, start_page_index, piece_height=2000):
    """
    Slices an image into smaller pieces of specified height.
    Supports animated images (GIF, WEBP) and processes all frames.

    Args:
        image_path (str): Path to the input image.
        output_folder (str): Path to the output folder.
        manga_title (str): Manga title.
        chapter_index (int): Chapter index.
        start_page_index (int): Starting page index for naming output slices.
        piece_height (int): Height of each piece in pixels.
    """
    manga_title = manga_title.lower().replace(" ", "_")
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        is_animated = getattr(img, "is_animated", False)

        print(f"Original image size: {img_width}x{img_height}, Animated: {is_animated}")

        current_page_index = start_page_index

        # Handle static images
        if not is_animated:
            current_page_index = slice_static_image(
                img, output_folder, manga_title, chapter_index, current_page_index, piece_height
            )
        else:
            # Handle animated images frame by frame
            frame_index = 0
            for frame in ImageSequence.Iterator(img):
                frame = frame.copy()
                frame_output_folder = os.path.join(output_folder, f"frame_{frame_index:02}")
                os.makedirs(frame_output_folder, exist_ok=True)

                current_page_index = slice_static_image(
                    frame, frame_output_folder, manga_title, chapter_index, current_page_index, piece_height
                )
                frame_index += 1

        return current_page_index


def slice_static_image(img, output_folder, manga_title, chapter_index, start_page_index, piece_height):
    """
    Slices a single static image into smaller pieces.

    Args:
        img (PIL.Image.Image): The image to be sliced.
        output_folder (str): Path to the output folder.
        manga_title (str): Manga title.
        chapter_index (int): Chapter index.
        start_page_index (int): Starting page index for naming output slices.
        piece_height (int): Height of each piece in pixels.
    """
    img_width, img_height = img.size
    current_page_index = start_page_index

    if img_height <= piece_height:
        output_filename = f"chapter{chapter_index}_{current_page_index:02}.png"
        output_path = os.path.join(output_folder, output_filename)
        img.save(output_path, "PNG")  # Save as PNG to preserve transparency if any
        print(f"Saved: {output_path}")
        current_page_index += 1
    else:
        for cut_number in range(0, img_height, piece_height):
            box = (0, cut_number, img_width, min(cut_number + piece_height, img_height))
            piece = img.crop(box)

            output_filename = f"chapter{chapter_index}_{current_page_index:02}.png"
            output_path = os.path.join(output_folder, output_filename)
            piece.save(output_path, "PNG")
            print(f"Saved: {output_path}")
            current_page_index += 1

    return current_page_index


def download_images_for_chapter(driver, chapter_url, manga_title, chapter_index):
    print(f"Processing Chapter {chapter_index}: {chapter_url}")
    driver.get(chapter_url)

    try:
        # Wait for the images to load within the viewer
        WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#viewer .item img.page-img"))
        )
    except Exception as e:
        print(f"Images not found for Chapter {chapter_index}: {e}")
        return

    # Find all image elements within the viewer
    image_elements = driver.find_elements(By.CSS_SELECTOR, "#viewer .item img.page-img")
    if not image_elements:
        print(f"No images found for Chapter {chapter_index}")
        return

    # Create the folder to store images for the chapter
    folder_name = os.path.join(manga_title.lower().replace(" ", "_"), f"chapter_{chapter_index}")
    os.makedirs(folder_name, exist_ok=True)

    current_page_index = 1
    for idx, img in enumerate(image_elements):
        img_url = img.get_attribute("src")
        if img_url and img_url.startswith("https"):
            try:
                # Fetch the image data
                response = requests.get(img_url, timeout=10)
                response.raise_for_status()

                # Get the file extension from the URL
                file_extension = img_url.split(".")[-1].split("?")[0].lower()
                if file_extension not in ["webp", "gif", "jpg", "jpeg", "png"]:
                    file_extension = "webp"  # Default to webp if format is ambiguous

                temp_image_path = os.path.join(
                    folder_name, f"chapter{chapter_index}_{current_page_index:02}.{file_extension}"
                )

                # Save the image directly in its original format
                with open(temp_image_path, "wb") as img_file:
                    img_file.write(response.content)

                print(f"Saved: {temp_image_path}")
                current_page_index += 1

            except Exception as e:
                print(f"Error downloading or saving image {img_url}: {e}")


def scrape_chapters(driver, manga_url):
    print(f"Scraping chapters from {manga_url}")
    driver.get(manga_url)
    baseUrl = "https://zbato.com"

    try:
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.main'))
        )
    except Exception as e:
        print(f"Failed to load content: {e}")
        return []

    try:
        # Locate the chapter list container
        chapter_list = driver.find_element(By.CSS_SELECTOR, 'div.main')
        # Locate all chapter links
        chapter_links = chapter_list.find_elements(By.CSS_SELECTOR, 'a.visited.chapt')
    except Exception as e:
        print(f"Failed to locate chapter list: {e}")
        return []

    chapters = []
    for link in chapter_links:
        href = link.get_attribute("href")
        if href and not href.startswith("http"):
            href = baseUrl + href  # Ensure full URL is formed

        # Extract the chapter number from the <b> tag
        try:
            chapter_text = link.find_element(By.TAG_NAME, "b").text.strip()  # Extract text from <b>
            chapter_number_match = re.search(r"Chapter\s*(\d+)", chapter_text)
            if chapter_number_match:
                chapter_number = int(chapter_number_match.group(1))
                chapters.append((chapter_number, href))
        except Exception as e:
            print(f"Error extracting chapter number for {href}: {e}")

    # Sort chapters numerically
    chapters.sort(key=lambda x: x[0])
    print(f"Found {len(chapters)} chapters.")
    return chapters

# Main function
def main():
    manga_url = "https://battwo.com/title/97485-the-predator-s-fiancee-official"
    manga_title = "The Predator's Fiancée"

    driver = setup_driver()

    try:
        chapters = scrape_chapters(driver, manga_url)
        for chapter_number, chapter_url in chapters[:111]:
            download_images_for_chapter(driver, chapter_url, manga_title, chapter_number)
    finally:
        driver.quit()

    print("Download completed!")


# Run the script
if __name__ == "__main__":
    main()