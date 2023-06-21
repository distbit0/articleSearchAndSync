import json
import utils
from utils import getConfig
import os
import glob


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
                    url = utils.makeDiscoursePrintable(url)
                    if url.lower() not in "\n".join(allAddedUrls).lower():
                        urlsToAdd[subject].append(url)

    return urlsToAdd


def addUrlsToFiles(urlsToAdd):
    atVoiceURLFileFolder = getConfig()["atVoiceURLFileFolder"]
    for subject in urlsToAdd:
        with open(atVoiceURLFileFolder + subject + ".txt", "w") as f:
            f.write("\n".join(urlsToAdd[subject]))


def deleteFilesMarkedToDelete():
    atVoiceFolder = getConfig()["atVoiceFolderPath"]
    articleFileFolder = getConfig()["articleFileFolder"]
    markedAsDeletedFile = atVoiceFolder + "/.config/_markedAsDeleted.rlst"
    markedAsDeletedText = open(markedAsDeletedFile).read().strip()
    markedAsDeletedFiles = markedAsDeletedText.split("\n:")[-1].split("\n")[1:]
    for file_path in markedAsDeletedFiles:
        fileName = file_path.split("/")[-1].split("\t")[0]
        utils.delete_files_with_name(articleFileFolder, fileName)


def updateUrlListFiles(folder_path):
    # Loop over all subdirectories using os.walk
    for dirpath, dirs, files in os.walk(folder_path):
        # Filter out the html and mhtml files
        html_files = [f for f in files if f.endswith((".html", ".mhtml"))]
        urls = []

        # If there are html or mhtml files in the directory
        if html_files:
            # Loop over each file
            for file in html_files:
                # Full file path
                file_path = os.path.join(dirpath, file)
                # Get url of file
                url = utils.getUrlOfArticle(file_path)
                urls.append(url)

            # Write the urls to a text file in the directory
            with open(os.path.join(dirpath, "articleUrls.txt"), "w") as f:
                for url in urls:
                    f.write(f"{url}\n")


if __name__ == "__main__":
    updateUrlListFiles(getConfig()["articleFileFolder"])
    deleteFilesMarkedToDelete()
    extractedUrls = utils.getUrlsInLists()
    utils.addUrlToUrlFile(
        extractedUrls, utils.getAbsPath("../storage/alreadyAddedArticles.txt")
    )
    urlsToAdd = calcUrlsToAdd()
    addUrlsToFiles(urlsToAdd)
