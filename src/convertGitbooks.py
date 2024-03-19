from calendar import c
from hashlib import file_digest
import html
import os
import sys
from venv import create
from openai import file_from_path
from pyparsing import html_comment
import requests
import shutil
from bs4 import BeautifulSoup
from utils import getUrlOfArticle, getConfig
import pysnooper


sys.path.append("/home/pimania/dev/convertLinks")
from convertLinks import main


def getSrcUrlOfArticle(articlePath):
    htmlText = open(articlePath, errors="ignore").read()
    if '" rel="nofollow">Link to original</a></p>' in htmlText:
        srcUrl = htmlText.split('" rel="nofollow">Link to original</a></p>')[0]
        srcUrl = srcUrl.split('><a href="')[-1]
        return srcUrl
    return None


def process_articles_in_directory(directory):
    filesToConvert = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".html") or file.endswith(".mhtml"):
                file_path = os.path.join(root, file)
                url = getUrlOfArticle(file_path)
                if "gist.github.com" in url:
                    srcUrl = getSrcUrlOfArticle(file_path)
                    if srcUrl:
                        filesToConvert.append([file_path, srcUrl, url])

    print("files to convert: ", len(filesToConvert))
    for i, article in enumerate(filesToConvert):
        file_path, url, gitBookUrl = article
        # print("\n\n\n\n")
        # print(i, "of ", len(filesToConvert), " ", file_path, url)
        # print("converting url: ", url)
        # newUrls = main(url, False, True)
        # newUrl = newUrls[0] if newUrls else False

        # if not newUrl:
        #     print("deleting file because of issue with url: ", url, file_path, "\n\n")
        #     os.remove(file_path)
        #     continue

        # print("new url: ", newUrl)
        # response = requests.get(newUrl)
        # soup = BeautifulSoup(response.text, "html.parser")
        # html_content = str(soup)
        # html_content = f"<!-- Hyperionics-OriginHtml {newUrl}-->\n" + html_content
        # print(html_content[:100])
        # with open(file_path, "w") as file:
        #     file.write(html_content)


def createFiles(mapOfFiles):
    for url in mapOfFiles:
        filePath = mapOfFiles[url]
        try:
            os.remove(filePath)
            print("deleted file: ", filePath)
        except OSError as e:
            print(f"Error deleting {filePath}: {e}")
        filePath = filePath.strip(" ")
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        html_content = str(soup)
        html_content = f"<!-- Hyperionics-OriginHtml {url}-->\n" + html_content
        with open(filePath, "w") as file:
            print("about to write: ", filePath, url)
            file.write(html_content)
        open(filePath, "r").read()


directory = getConfig()["articleFileFolder"]
# process_articles_in_directory(directory)
# createFiles()
