import json
import os
import requests
import re

# Function to download an image from a URL
def download_image(url, save_path):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Check if the request was successful
        with open(save_path, 'wb') as file:
            file.write(response.content)  # Save the image content to a file
        print(f"Downloaded: {save_path}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")

# Load the JSON data from a file (replace 'data.json' with your file path)
with open('data.json', 'r') as file:
    data = json.load(file)

# Create a directory to save the images (optional)
if not os.path.exists('downloaded_images'):
    os.makedirs('downloaded_images')

# Function to extract manga name and chapter from the URL
def extract_manga_info(url: str):
    # Regular expression pattern to extract manga name and chapter
    pattern = r"manga/([^/]+)/([^/]+)/([^/]+)-([^/]+)"
    match = re.search(pattern, url)

    if match:
        manga_name = match.group(1)  # Extract manga name
        chapter = match.group(2)  # Extract chapter
        return manga_name, chapter
    else:
        return None, None

# Extract manga name and chapter from the first image URL
first_image_url = data.get('list', [])[0].get('src', {}).get('original', "")
Name, episode = extract_manga_info(first_image_url)

# Loop through each item in the "list" key of the JSON data
for index, item in enumerate(data.get('list', [])):
    image_url = item.get('upscale_img')
    if image_url:
        # Generate a unique name for each image
        image_name = f"{episode}_{index+1}.jpg"
        save_path = os.path.join(f'downloaded_images/{Name}', image_name)

        # Create the directory for the manga name if it doesn't exist
        if not os.path.exists(os.path.dirname(save_path)):
            os.makedirs(os.path.dirname(save_path))
        
        # Download the image and save it
        download_image(image_url, save_path)