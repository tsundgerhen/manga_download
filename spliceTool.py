import os
from PIL import Image
from natsort import natsorted


def split_image(
    image_path, 
    output_base_folder, 
    manga_title, 
    chapter_number, 
    start_page_index=1, 
    piece_height=1600
):
    # Prepare folder structure
    manga_title = manga_title.lower().replace(" ", "_")
    chapter_folder = os.path.join(output_base_folder, manga_title, f"chapter_{chapter_number}")
    os.makedirs(chapter_folder, exist_ok=True)

    # Open the original image
    with Image.open(image_path) as img:
        img_width, img_height = img.size
        current_page_index = start_page_index
        file_extension = os.path.splitext(image_path)[1].lower()  # Preserve original format

        # If image height is less than or equal to the piece height, save as a single piece
        if img_height <= piece_height:
            output_filename = f"page_{current_page_index}{file_extension}"
            output_path = os.path.join(chapter_folder, output_filename)
            img.save(output_path, quality=100)  # Preserve quality
            current_page_index += 1
        else:
            # Split the image into pieces
            num_pieces = img_height // piece_height
            for cut_number in range(num_pieces):
                box = (0, cut_number * piece_height, img_width, (cut_number + 1) * piece_height)
                piece = img.crop(box)
                output_filename = f"page_{current_page_index}{file_extension}"
                output_path = os.path.join(chapter_folder, output_filename)
                piece.save(output_path, quality=100)  # Preserve quality
                current_page_index += 1

            # Handle the remainder (if any)
            remainder = img_height % piece_height
            if remainder > 0:
                box = (0, img_height - remainder, img_width, img_height)
                piece = img.crop(box)
                output_filename = f"page_{current_page_index}{file_extension}"
                output_path = os.path.join(chapter_folder, output_filename)
                piece.save(output_path, quality=100)  # Preserve quality
                current_page_index += 1

    return current_page_index


def process_manga_folder(input_folder, output_folder, image_height):
    for root, _, files in os.walk(input_folder):
        relative_path = os.path.relpath(root, input_folder)
        parts = root.split(os.sep)

        # Skip folders without valid structure
        if len(parts) < 2:
            print(f"Skipping folder: {root} (not a valid manga/chapter structure)")
            continue

        # Extract manga title and chapter folder
        manga_title = parts[0]
        chapter_folder = parts[1]

        print(f"Processing: Manga '{manga_title}', Chapter '{chapter_folder}'")

        start_page_index = 1
        for file_name in natsorted(files):
            if file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                image_path = os.path.join(root, file_name)
                print(f"  Splitting: {image_path}")
                start_page_index = split_image(
                    image_path=image_path,
                    output_base_folder=output_folder,
                    manga_title=manga_title,
                    chapter_number=chapter_folder,
                    start_page_index=start_page_index,
                    piece_height=image_height,
                )

    print("Processing complete!")


if __name__ == "__main__":
    # Define the input and output folders
    input_folder = "The reason why raeliana ended up at the duke’s mansion"  # Replace with the path to your manga folder
    output_folder = "SPLIT The reason why raeliana ended up at the duke’s mansion"  # Replace with the desired output folder
    image_height = 2000  # You can adjust this value as needed
    
    # Process all images in the manga folder
    process_manga_folder(input_folder, output_folder, image_height)