import os
import sys
import requests
import shutil
from bs4 import BeautifulSoup
from utils import getUrlOfArticle, getConfig
import pysnooper

sys.path.append("/home/pimania/dev/convertLinks")
from convertLinks import main


def process_articles_in_directory(directory):
    filesToConvert = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".html") or file.endswith(".mhtml"):
                file_path = os.path.join(root, file)
                url = getUrlOfArticle(file_path)
                if url and ("docs." in url and "google" not in url) or "gitbook" in url:
                    filesToConvert.append(file_path)

    for i, file_path in enumerate(filesToConvert):
        print(i, "of ", len(filesToConvert), " ", file_path, url)
        url = getUrlOfArticle(file_path)
        newUrls = main(url, False, True)
        newUrl = newUrls[0] if newUrls else False

        if not newUrl:
            print("issue with url: ", url)
            newUrl = main(file_path, False, True)[0]
            print("new url: ", newUrl)

        response = requests.get(newUrl)
        soup = BeautifulSoup(response.text, "html.parser")
        html_content = str(soup)
        html_content = f"<!-- Hyperionics-OriginHtml {newUrl}-->\n" + html_content
        print(html_content[:200])
        with open(file_path, "w") as file:
            file.write(html_content)
        # if "problematic" in file_path:
        #     shutil.move(file_path, directory)


directory = getConfig()["articleFileFolder"]
process_articles_in_directory(directory)
