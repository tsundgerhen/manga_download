import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
import re
from io import BytesIO
from requests.exceptions import RequestException
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By  
from urllib.parse import urljoin

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

# https://kingofshojo.com script section
# Function to download images for a specific chapter
def kingOfShojo_download_images_for_chapter(chapter_number, chapter_url, manga_title):
    print(f"Processing Chapter {chapter_number}: {chapter_url}")
    
    try:
        response = requests.get(chapter_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Failed to fetch chapter page: {e}")
        return

    img_tags = soup.find_all("img", src=True)
    valid_imgs = []

    for img in img_tags:
        img_alt = img.get("alt", "")
        img_title = img.get("title", "")
        img_src = img.get("src", "")

        # Check if alt starts with sequential numbering and title matches the chapter info
        if re.match(r"^\d{2,3}$", img_alt) and f"{manga_title} Chapter {chapter_number}" in img_title:
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


# Function to scrape chapters from the chapter list
def kingOfShojo_scrape_chapters(manga_url):
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
def kingOfShojo_main():
    manga_url = "https://kingofshojo.com/manga/seduce-the-villains-father/"
    manga_title = "Seduce the Villain’s Father"  # Set manga title

    chapters = kingOfShojo_scrape_chapters(manga_url)
    for chapter_number, chapter_url in chapters:
        kingOfShojo_download_images_for_chapter(chapter_number, chapter_url, manga_title)

    print("Download completed!")

# https://manhuaus.com script section
# Function to download images for a specific chapter and split large images into smaller pieces
def manhuaus_download_images_for_chapter(chapter_number, chapter_url, manga_url):
    # Extract the manga name from the URL
    manga_title = extract_manga_title(manga_url)  # Get the manga title from the URL
    
    print(f"Processing Chapter {chapter_number} at {chapter_url}")

    # Send a GET request to the chapter page
    response = requests.get(chapter_url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Find the images inside the chapter page
    image_tags = soup.find_all("img", class_="wp-manga-chapter-img")

    if image_tags:
        print(f"Found {len(image_tags)} images in Chapter {chapter_number}")
        
        # Create folder with manga title and chapter number
        folder_name = f"{manga_title}/chapter_{chapter_number}"
        os.makedirs(folder_name, exist_ok=True)

        current_page_index = 1  # Start from page 1
        for idx, img_tag in enumerate(image_tags):
            img_url = img_tag.get("data-src")  # Image URL is often in 'data-src' for lazy loading
            if img_url:
                try:
                    # Download the image
                    img_data = requests.get(img_url).content
                    img_path = os.path.join(folder_name, f"temp_page_{idx + 1}.jpg")
                    
                    # Save the image temporarily
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)
                    print(f"Downloaded page {idx + 1} for Chapter {chapter_number}")

                    # Now split the image if needed
                    current_page_index = split_image(img_path, folder_name, manga_title, chapter_number, current_page_index)
                    os.remove(img_path)  # Remove the temporary image after splitting
                    
                except Exception as e:
                    print(f"Error downloading page {idx + 1}: {e}")
    else:
        print(f"No images found for Chapter {chapter_number}.")


# Function to extract manga title from manga URL
def extract_manga_title(manga_url):
    # Extract the manga name from the URL (the part after "/manga/")
    manga_title = manga_url.split("/manga/")[-1]
    
    # Replace hyphens with spaces and capitalize the title
    manga_title = manga_title.replace("-", " ").title()
    
    return manga_title


# Function to scrape the list of chapters from the manga list page
def manhuaus_scrape_chapters(manga_url):
    print(f"Scraping chapters for {manga_url}")
    
    # Send a GET request to the manga list page
    response = requests.get(manga_url)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find the div that contains the chapter list
    chapter_list_div = soup.find("div", class_="page-content-listing single-page")
    chapter_links = chapter_list_div.find_all("a", href=True)  # Find all <a> tags with href attribute
    
    chapters = []
    for link in chapter_links:
        href = link.get("href")
        if href:
            # Extract chapter number from the URL
            if "chapter-" in href:
                chapter_number = href.split("chapter-")[-1].split("/")[0]
                
                # Filter out non-numeric chapters
                try:
                    int(chapter_number)  # Check if it can be converted to an integer
                    chapters.append((chapter_number, href))
                except ValueError:
                    print(f"Skipping non-numeric chapter: {chapter_number}")
    
    # Sort chapters numerically to ensure correct order
    chapters.sort(key=lambda x: int(x[0]))  # Ensure sorting by chapter number (ascending)
    
    print(f"Found {len(chapters)} chapters.")
    return chapters


# Main function to start the script
def manhuaus_main():
    manga_url = "https://manhuaus.com/manga/the-reincarnation-of-the-forbidden-archmage"
    
    # Scrape the chapters
    chapters = manhuaus_scrape_chapters(manga_url)
    
    # Process each chapter starting from the first one
    for chapter_number, chapter_href in chapters:
        chapter_url = f"{chapter_href}"
        manhuaus_download_images_for_chapter(chapter_number, chapter_url, manga_url)

    print("Download completed!")


manga_title = "Get Schooled"
chaptersName = []  # Initialize chapter globally to store chapter titles

# Function to download images for a specific chapter
def naver_download_images_for_chapter(chapter_number, chapter_url, manga_url):
    global chaptersName  # Use the global chapter variable
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
        
        # Use regular expression to extract the chapter number from chapter name
        chapter_number_str = re.match(r"(\d+)", chaptersName[chapter_number - 1]).group(1)
        
        folder_name = f"{manga_title}/chapter-{chapter_number_str}"  # Use the extracted chapter number
        os.makedirs(folder_name, exist_ok=True)

        current_page_index = 1
        for idx, img_tag in enumerate(image_tags):
            img_url = img_tag.get("src")
            if img_url and "thumbnail" not in img_url:  # Skip thumbnails by checking the URL
                try:
                    # Add User-Agent header to simulate a real browser request
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
                    }

                    img_data = requests.get(img_url, headers=headers)
                    img_data.raise_for_status()  # Check if the image download was successful

                    # Save image as a temporary file
                    img_path = f"{folder_name}/{chaptersName[chapter_number - 1]}_{idx + 1}.png"
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data.content)  # Save the image

                    # Optionally split large images into smaller pieces (if necessary)
                    current_page_index = split_image(img_path, folder_name, manga_title, chapter_number, current_page_index)

                    # Remove the temporary image after splitting
                    os.remove(img_path)
                    print(f"Uploaded {img_path}")

                except RequestException as e:
                    print(f"Error downloading page {idx + 1} at {img_url}: {e}")
                except Exception as e:
                    print(f"Unexpected error while processing image {idx + 1}: {e}")
    except Exception as e:
        print(f"Error processing Chapter {chapter_number}: {e}")


# Scrape chapters from the manga list page
def naver_scrape_chapters_with_selenium(manga_url):
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
        
        global chaptersName
        chapter = soup.find_all("p", class_=lambda class_name: class_name and "EpisodeListList__title_area" in class_name)

        chaptersName = []  # Initialize an empty list to store chapter names

        # Now iterate over the found <p> tags and extract the <span> inside them
        for p_tag in chapter:
            span_tag = p_tag.find("span", class_=lambda class_name: class_name and "EpisodeListList__title" in class_name)
            if span_tag:  # Check if the <span> tag was found
                chaptersName.append(span_tag.text)  # Save the text content of the <span> tag to chaptersName

# Print the list of chapter names
            
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
def naver_main(manga_url):
    manga_url = "https://comic.naver.com/webtoon/list?titleId=758037&page=8&sort=DESC"
    chapters = naver_scrape_chapters_with_selenium(manga_url)

    for chapter_number, chapter_href in enumerate(chapters, start=1):  # Enumerate to generate chapter numbers
        naver_download_images_for_chapter(chapter_number, chapter_href, manga_url)

    print("Download completed!")

#battwo section
# Download images for a chapter
def battwo_download_images_for_chapter(driver, chapter_url, manga_title, chapter_index):
    print(f"Processing Chapter {chapter_index}: {chapter_url}")
    driver.get(chapter_url)

    # Wait for the viewer div to load
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "viewer"))
        )
    except Exception as e:
        print(f"Viewer not found: {e}")
        return

    viewer_div = driver.find_element(By.ID, "viewer")
    img_elements = viewer_div.find_elements(By.TAG_NAME, "img")

    if not img_elements:
        print(f"No images found for Chapter {chapter_index}")
        return

    folder_name = os.path.join(manga_title.lower().replace(" ", "_"), f"chapter_{chapter_index}")
    os.makedirs(folder_name, exist_ok=True)

    current_page_index = 1
    for idx, img in enumerate(img_elements):
        img_url = img.get_attribute("src")

        # Check if the image is the best quality by URL
        if ".webp" in img_url or ".jpg" in img_url:  # Prefer webp or high res jpg
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
def battwo_scrape_chapters(driver, manga_url):
    print(f"Scraping chapters from {manga_url}")
    driver.get(manga_url)

    # Wait for the main div to load
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "main"))
        )
    except Exception as e:
        print(f"Failed to load main div: {e}")
        return []

    main_div = driver.find_element(By.CLASS_NAME, "main")
    chapter_links = main_div.find_elements(By.CSS_SELECTOR, "a.chapt")

    chapters = []
    for link in chapter_links:
        href = link.get_attribute("href")
        chapter_number_match = re.search(r"chapter/(\d+)", href)
        if chapter_number_match:
            chapter_number = int(chapter_number_match.group(1))
            chapters.append((chapter_number, href))

    chapters.sort(key=lambda x: x[0])  # Sort chapters numerically
    print(f"Found {len(chapters)} chapters.")
    return chapters


# Main function
def battwo_main():
    manga_url = "https://battwo.com/series/141768/secret-playlist-official"
    manga_title = "Secret Playlist Official"

    driver = setup_driver()

    try:
        chapters = battwo_scrape_chapters(driver, manga_url)
        for chapter_index, (chapter_number, chapter_url) in enumerate(chapters, start=1):
            battwo_download_images_for_chapter(driver, chapter_url, manga_title, chapter_index)
    finally:
        driver.quit()

    print("Download completed!")


# bato section
# Function to download images for a specific chapter and split large images
def bato_download_images_for_chapter(chapter_number, chapter_url, manga_url):
    manga_title = bato_extract_manga_title(manga_url)  # Get the manga title
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
def bato_extract_manga_title(manga_url):
    manga_title = manga_url.split("/")[-1]
    manga_title = re.sub(r"[<>:\"/\\|?*]", "", manga_title)  # Remove invalid characters
    return manga_title

# Function to scrape chapter list
def bato_scrape_chapters(manga_url):
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
def bato_main():
    manga_url = "https://bato.ing/title/84772-olgami"
    chapters = bato_scrape_chapters(manga_url)

    for chapter_number, chapter_href in chapters:
        bato_download_images_for_chapter(chapter_number, chapter_href, manga_url)

    print("Download completed!")



# Run the script
if __name__ == "__main__":
   kingOfShojo_main()
   manhuaus_main()
   naver_main()
   battwo_main()
