from calendar import c
import html
import os
import sys
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
                    url = getSrcUrlOfArticle(file_path)
                    if url:
                        filesToConvert.append([file_path, url])

    print("files to convert: ", len(filesToConvert))
    for i, article in enumerate(filesToConvert):
        print("\n\n\n\n")
        # print(i, "of ", len(filesToConvert), " ", file_path, url)
        file_path, url = article
        print("converting url: ", url)
        # newUrls = main(url, False, True)
        # newUrl = newUrls[0] if newUrls else False
        # isHidden = file_path.split("/")[-1][0] == "."

        # if not newUrl:
        #     if "/home/pimania/" in url:
        #         print("issue with url because of home directory")
        #     print(
        #         "issue with url: ",
        #         url,
        #         "file path: ",
        #         file_path,
        #         "is hidden: ",
        #         isHidden,
        #     )
        #     # os.remove(file_path)
        #     continue

        # print("new url: ", newUrl)
        # response = requests.get(newUrl)
        # soup = BeautifulSoup(response.text, "html.parser")
        # html_content = str(soup)
        # html_content = f"<!-- Hyperionics-OriginHtml {newUrl}-->\n" + html_content
        # print(html_content[:100])
        # with open(file_path, "w") as file:
        #     file.write(html_content)


directory = getConfig()["articleFileFolder"]
process_articles_in_directory(directory)
