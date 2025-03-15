import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from requests.exceptions import RequestException
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time

manga_title = "On My Way To See My Mom"
chaptersName = []  # Initialize chapter globally to store chapter titles

# Function to download images for a specific chapter
def download_images_for_chapter(chapter_number, chapter_url):
    """
    Downloads images from a given chapter URL, creates a folder for each chapter, 
    and processes the images.
    """
    global chaptersName  # Ensure global access to chapter names
    
    # Extract chapter number (fallback to direct numbering if regex fails)
    try:
        chapter_number_str = re.match(r"(\d+)", chaptersName[chapter_number - 1]).group(1)
    except (IndexError, AttributeError):
        chapter_number_str = str(chapter_number)

    print(f"Processing Chapter {chapter_number_str} at {chapter_url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        response = requests.get(chapter_url, headers=headers)  
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find images (check both 'data-src' and 'src')
        image_tags = soup.find_all("img", alt="comic content")
        if not image_tags:
            print(f"No images found for Chapter {chapter_number}.")
            return

        print(f"Found {len(image_tags)} images in Chapter {chapter_number}")

        # Create folder for chapter
        folder_name = f"{manga_title}/chapter-{chapter_number_str}"
        os.makedirs(folder_name, exist_ok=True)

        current_page_index = 1
        for idx, img_tag in enumerate(image_tags):
            img_url = img_tag.get("data-src") or img_tag.get("src")
            if img_url and "thumbnail" not in img_url:  
                try:
                    img_data = requests.get(img_url, headers=headers)
                    img_data.raise_for_status()

                    # Save image temporarily
                    img_path = f"{folder_name}/temp_{idx + 1}.png"
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data.content)

                    # Split large images
                    current_page_index = split_image(img_path, folder_name, manga_title, chapter_number, current_page_index)

                    # Remove temp file after processing
                    os.remove(img_path)
                    print(f"Downloaded: {img_path}")

                except RequestException as e:
                    print(f"Error downloading image {idx + 1}: {e}")
                except Exception as e:
                    print(f"Unexpected error with image {idx + 1}: {e}")

    except Exception as e:
        print(f"Error processing Chapter {chapter_number}: {e}")
# Split large images into smaller pieces
def split_image(image_path, output_folder, manga_title, chapter_number, start_page_index, piece_height=1600):
    """
    Splits an image into smaller pieces of a specified height without altering the original quality or format.

    Args:
        image_path (str): Path to the original image file.
        output_folder (str): Folder where the output images will be stored.
        manga_title (str): Title of the manga.
        chapter_number (int): Chapter number of the manga.
        start_page_index (int): Starting page index for naming the pieces.
        piece_height (int): Height of each piece (default: 1600 pixels).
    
    Returns:
        int: Next page index after processing all pieces.
    """
    manga_title = manga_title.lower().replace(" ", "_")
    os.makedirs(output_folder, exist_ok=True)
    chapter_number_str = re.match(r"(\d+)", chaptersName[chapter_number - 1]).group(1)

    with Image.open(image_path) as img:
        img_width, img_height = img.size
        current_page_index = start_page_index
        file_extension = os.path.splitext(image_path)[1].lower()  # Preserve original file format

        if img_height <= piece_height:
            # If the image is smaller than the piece height, save as a single file
            output_filename = f"chapter-{chapter_number_str}-{current_page_index}{file_extension}"
            output_path = os.path.join(output_folder, output_filename)
            img.save(output_path, quality=100)  # Preserve quality
            current_page_index += 1
        else:
            # Split the image into multiple pieces
            num_pieces = img_height // piece_height
            for cut_number in range(num_pieces):
                box = (0, cut_number * piece_height, img_width, (cut_number + 1) * piece_height)
                piece = img.crop(box)

                output_filename = f"chapter-{chapter_number_str}-{current_page_index}{file_extension}"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, quality=100)  # Preserve quality
                current_page_index += 1

            # Handle the remainder (if any)
            remainder = img_height % piece_height
            if remainder > 0:
                box = (0, img_height - remainder, img_width, img_height)
                piece = img.crop(box)

                output_filename = f"chapter-{chapter_number_str}-{current_page_index}{file_extension}"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, quality=100)  # Preserve quality
                current_page_index += 1

        return current_page_index

# Scrape chapters from the manga list page
def scrape_chapters_with_selenium(manga_url):
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
        
        global chaptersName
        chapter = soup.find_all("p", class_=lambda class_name: class_name and "EpisodeListList__title_area" in class_name)

        chaptersNameInPage = []  # Initialize an empty list to store chapter names
        have_next_page = False
        # Now iterate over the found <p> tags and extract the <span> inside them
        for p_tag in chapter:
            span_tag = p_tag.find("span", class_=lambda class_name: class_name and "EpisodeListList__title" in class_name)
            if span_tag:  # Check if the <span> tag was found
                chaptersNameInPage.append(span_tag.text)  # Save the text content of the <span> tag to chaptersName
                chapter_number_str = re.match(r"(\d+)", chaptersNameInPage[0]).group(1)
                chapter_number = int(chapter_number_str)  # Convert to integer

                # Determine if there's a next page
                have_next_page = chapter_number > 20

        chaptersName.extend(chaptersNameInPage) 
        for li in chapter_list_items:
            link = li.find("a", href=True)
            if link:
                href = link.get("href")
                full_url = f"{base_url}{href}"
                chapters.append((len(chaptersNameInPage) - 1, full_url))  # Add both chapter number and URL as a tuple

        

        return chapters, have_next_page

    except Exception as e:
        print(f"Error occurred: {e}")
        return [], False  # Return empty list and False for next page

    finally:
        driver.quit()  # Close the browser

def scrape_all_chapters(manga_url):
    chapters = []  # To store all chapter links  # To store chapter names
    current_page = 1  # Start from the first page
    global chaptersName
    # Initial scrape for the first page
    temp_pages, has_next_page = scrape_chapters_with_selenium(manga_url)
    chapters.extend(temp_pages)  # Add the first page's chapters to the list

    # Loop while there are more pages
    while has_next_page:
        current_page += 1  # Increment page number
        next_page_url = f"{manga_url}&page={current_page}&sort=DESC"  # Update URL for the next page
        temp_pages, has_next_page = scrape_chapters_with_selenium(next_page_url)
        chapters.extend(temp_pages)  # Add the chapters from the current page to the list

    # Filter chapters based on names in `chaptersName` (global)
    filtered_chapters = []
    filtered_chapters_names = []
    
    for chapter_number, chapter_href in enumerate(chapters, start=1):  # Start at 1 to match the chapter index
        # Extract the correct chapter name from the global chaptersName list
        chapter_name = chaptersName[chapter_number - 1]  # Adjusting for zero-based index
        if re.match(r"\d+화$", chapter_name):  # Ensure the chapter name ends with digits followed by '화'
            filtered_chapters.append(chapter_href)  # Add the chapter link to the filtered list
            filtered_chapters_names.append(chapter_name)  # Add the valid chapter name to the filtered list

    # Update global variables with the filtered chapters and names
    chaptersName = filtered_chapters_names
    chapters = filtered_chapters


    # Reverse the final list
    chapters.reverse()
    chaptersName.reverse()
    return chapters, filtered_chapters_names

# Main function
def main():
    manga_url = "https://comic.naver.com/webtoon/list?titleId=814753"
    global manga_title
    manga_title = "Weapon creater"
    
    # Scrape all chapters
    chapters, chapters_names = scrape_all_chapters(manga_url)

    # Print chapter links
    for chapter_number, chapter_tuple in enumerate(chapters[0:], start=1):
        chapter_href = chapter_tuple[1]  # Extract the correct URL
        download_images_for_chapter(chapter_number, chapter_href)  # Pass the correct chapter number and URL

    print(f"Total chapters found: {len(chapters)}")

if __name__ == "__main__":
    main()