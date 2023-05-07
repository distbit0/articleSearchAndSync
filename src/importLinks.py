import json
import utils
from utils import getConfig


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
    markedAsDeletedFile = atVoiceFolder + "/.config/marked as deleted.rlst"
    markedAsDeletedText = open(markedAsDeletedFile).read().strip()
    markedAsDeletedFiles = markedAsDeletedText.split("\n:")[-1].split("\n")[1:]
    for file_path in markedAsDeletedFiles:
        fileName = file_path.split("/")[-1]
        utils.delete_files_with_name(articleFileFolder, fileName)


if __name__ == "__main__":
    deleteFilesMarkedToDelete()
    extractedUrls = utils.getUrlsInLists()
    utils.addUrlToUrlFile(
        extractedUrls, utils.getAbsPath("../storage/alreadyAddedArticles.txt")
    )
    urlsToAdd = calcUrlsToAdd()
    addUrlsToFiles(urlsToAdd)
