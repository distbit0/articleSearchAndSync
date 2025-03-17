import os
import shutil

# Directory to move files from
root_dir = "/home/pimania/ebooks/"

# Files to ignore
ignore_files = {"fileNamesAndHashes.txt", "articleUrls.txt"}

# Function to move files
for subdir, _, files in os.walk(root_dir):
    if subdir == root_dir:
        continue  # Skip the root directory itself
    for file in files:
        if file in ignore_files:
            continue
        source_path = os.path.join(subdir, file)
        destination_path = os.path.join(root_dir, file)

        # Resolve filename clashes
        if os.path.exists(destination_path):
            base, extension = os.path.splitext(file)
            counter = 1
            while os.path.exists(destination_path):
                destination_path = os.path.join(
                    root_dir, f"{base}_{counter}{extension}"
                )
                counter += 1

        # Move the file
        # print("Moving", source_path, "to", destination_path)
        shutil.move(source_path, destination_path)

print("Files moved successfully.")

# List remaining files in subdirectories
remaining_files = []
for subdir, _, files in os.walk(root_dir):
    if subdir == root_dir:
        continue  # Skip the root directory itself
    for file in files:
        remaining_files.append(os.path.join(subdir, file))

print("Remaining files in subdirectories:")
for file in remaining_files:
    print(file)
