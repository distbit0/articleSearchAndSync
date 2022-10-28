import json
import re
import utils
from utils import getConfig


def formatUrlFromBookMarks(url):
    if "ethresear.ch/t/" in url:
        if url.count("/") == 5:
            url += "/"
        url = re.sub(r"(https:\/\/ethresear.ch\/t\/.*\/.*)(/.*)", r"\1/print", url)
    return url


def getBookmarks():
    bookmarksFilePath = getConfig()["bookmarksFilePath"]
    with open(bookmarksFilePath) as f:
        bookmarks = json.load(f)
        return bookmarks


def calcUrlsToAdd():
    bookmarks = getBookmarks()
    urlsToAdd = {}

    allAddedUrls = utils.getUrlsFromFile(
        utils.getAbsPath("../storage/alreadyAddedArticles.txt")
    )
    bmBar = bookmarks["roots"]["bookmark_bar"]["children"]
    for folder in bmBar:
        if folder["type"] == "folder" and folder["name"] == "@Voice":
            for folder in folder["children"]:
                subject = folder["name"]
                urlsToAdd[subject] = []
                for link in folder["children"]:
                    url = link["url"]
                    url = utils.formatUrl(url)
                    url = formatUrlFromBookMarks(url)
                    if url.lower() not in "\n".join(allAddedUrls).lower():
                        urlsToAdd[subject].append(url)

    return urlsToAdd


def addUrlsToFiles(urlsToAdd):
    articleFileFolder = getConfig()["articleFileFolder"]
    for subject in urlsToAdd:
        with open(articleFileFolder + subject + ".txt", "w") as f:
            f.write("\n".join(urlsToAdd[subject]))


if __name__ == "__main__":
    extractedUrls = utils.getUrlsInLists()
    utils.addUrlToUrlFile(
        extractedUrls, utils.getAbsPath("../storage/alreadyAddedArticles.txt")
    )
    urlsToAdd = calcUrlsToAdd()
    addUrlsToFiles(urlsToAdd)
