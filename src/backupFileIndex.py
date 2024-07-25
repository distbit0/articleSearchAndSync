import os
import shutil
import json
from utils import getConfig

def backup_file_index():
    config = getConfig()
    source_dir = config["articleFileFolder"]
    backup_dir = config["backupFolderPath"]
    
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file in ["articleUrls.txt", "fileNamesAndHashes.txt"]:
                source_path = os.path.join(root, file)
                relative_path = os.path.relpath(source_path, source_dir)
                backup_path = os.path.join(backup_dir, relative_path)
                
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(source_path, backup_path)

if __name__ == "__main__":
    backup_file_index()
