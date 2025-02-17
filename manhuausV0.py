import os
import requests
from bs4 import BeautifulSoup
from PIL import Image

# Function to download images for a specific chapter and split large images into smaller pieces
def download_images_for_chapter(chapter_number, chapter_url, manga_url):
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


# Function to split an image into smaller pieces if its height exceeds the specified piece height
def split_image(image_path, output_folder, manga_title, chapter_number, start_page_index, piece_height=1600):
    # Process the manga_title to be lowercase and replace spaces with underscores
    manga_title = manga_title.lower().replace(" ", "_")
    
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        print(f"Original image size: {img_width}x{img_height}")

        current_page_index = start_page_index

        # If the image height is less than or equal to piece_height, save the whole image as one piece
        if img_height <= piece_height:
            # Convert the image to RGB mode if it's not already in a supported mode (like RGBA, P, etc.)
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")

            output_filename = f"{manga_title}-chapter{chapter_number}-{current_page_index}.jpg"
            output_path = os.path.join(output_folder, output_filename)
            img.save(output_path, "JPEG")
            print(f"Saved: {output_path}")
            current_page_index += 1
        else:
            # Calculate the number of pieces for splitting
            num_pieces = img_height // piece_height
            for cut_number in range(num_pieces):
                left = 0
                upper = cut_number * piece_height
                right = img_width
                lower = upper + piece_height

                box = (left, upper, right, lower)
                piece = img.crop(box)

                # Convert to RGB if the mode is not suitable for JPEG
                if piece.mode in ["RGBA", "P"]:
                    piece = piece.convert("RGB")

                output_filename = f"{manga_title}-chapter{chapter_number}-{current_page_index}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                print(f"Saved: {output_path}")
                current_page_index += 1

            # Save the remainder of the image (if any)
            remainder = img_height % piece_height
            if remainder > 0:
                left = 0
                upper = img_height - remainder
                right = img_width
                lower = img_height

                box = (left, upper, right, lower)
                piece = img.crop(box)

                # Convert to RGB if the mode is not suitable for JPEG
                if piece.mode in ["RGBA", "P"]:
                    piece = piece.convert("RGB")

                output_filename = f"{manga_title}-chapter{chapter_number}-{current_page_index}.jpg"
                output_path = os.path.join(output_folder, output_filename)
                piece.save(output_path, "JPEG")
                print(f"Saved: {output_path}")
                current_page_index += 1

        return current_page_index


# Function to scrape the list of chapters from the manga list page
def scrape_chapters(manga_url):
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
def main():
    manga_url = "https://manhuaus.com/manga/the-reincarnation-of-the-forbidden-archmage"
    
    # Scrape the chapters
    chapters = scrape_chapters(manga_url)
    
    # Process each chapter starting from the first one
    for chapter_number, chapter_href in chapters:
        chapter_url = f"{chapter_href}"
        download_images_for_chapter(chapter_number, chapter_url, manga_url)

    print("Download completed!")


# Run the script
if __name__ == "__main__":
    main()