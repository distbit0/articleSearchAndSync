import json
import utils
from utils import getConfig
import os
from collections import defaultdict
import hashlib
import reTitlePDFs


def getBookmarks():
    bookmarksFilePath = getConfig()["bookmarksFilePath"]
    with open(bookmarksFilePath) as f:
        bookmarks = json.load(f)
        return bookmarks


def calcUrlsToAdd(onlyRead=False):
    bookmarks = getBookmarks()
    urlsToAdd = {}

    if onlyRead:
        allAddedUrls = utils.getUrlsFromFile(
            utils.getAbsPath("../storage/markedAsReadArticles.txt")
        )
    else:
        allAddedUrls = utils.getUrlsFromFile(
            utils.getAbsPath("../storage/alreadyAddedArticles.txt")
        )
    bmBar = bookmarks["roots"]["bookmark_bar"]["children"]
    for folder in bmBar:
        if folder["type"] == "folder" and folder["name"] == "@Voice":
            for folder in folder["children"]:
                subject = folder["name"]
                if onlyRead and subject.lower() == "unread":
                    continue
                urlsToAdd[subject] = []
                for link in folder["children"]:
                    url = link["url"]
                    url = utils.formatUrl(url)
                    url = utils.makeDiscoursePrintable(url)
                    if url.lower() not in "\n".join(allAddedUrls).lower():
                        urlsToAdd[subject].append(url)

    return urlsToAdd


def generateUrlImportFilesForAtVoice(urlsToAdd):
    atVoiceURLFileFolder = getConfig()["atVoiceURLFileFolder"]
    linkText = "\n".join(["\n".join(urlsToAdd[subject]) for subject in urlsToAdd])
    with open(atVoiceURLFileFolder + "links" + ".txt", "w") as f:
        f.write(linkText)


def moveFilesMarkedToMove():
    atVoiceFolder = getConfig()["atVoiceFolderPath"]
    articleFileFolder = getConfig()["articleFileFolder"]
    markedToMoveFile = atVoiceFolder + "/.config/_markedToMove.rlst"
    markedToMoveText = open(markedToMoveFile).read().strip()
    markedToMoveFiles = markedToMoveText.split("\n:")[-1].split("\n")[1:]
    for file_path in markedToMoveFiles:
        fileName = file_path.split("/")[-1].split("\t")[0]
        utils.moveFilesWithNameToRootDir(articleFileFolder, fileName)


def markReadBookmarksAsRead():
    readUrls = calcUrlsToAdd(onlyRead=True)["AlreadyRead"]
    utils.markArticlesWithUrlsAsRead(readUrls, getConfig()["articleFileFolder"])


def deleteFilesMarkedToDelete():
    atVoiceFolder = getConfig()["atVoiceFolderPath"]
    articleFileFolder = getConfig()["articleFileFolder"]
    markedAsDeletedFile = atVoiceFolder + "/.config/_markedAsDeleted.rlst"
    markedAsDeletedText = open(markedAsDeletedFile).read().strip()
    markedAsDeletedFiles = markedAsDeletedText.split("\n:")[-1].split("\n")[1:]
    for file_path in markedAsDeletedFiles:
        fileName = file_path.split("/")[-1].split("\t")[0]
        utils.delete_files_with_name(articleFileFolder, fileName)


def hideArticlesMarkedAsRead():
    atVoiceFolder = getConfig()["atVoiceFolderPath"]
    articleFileFolder = getConfig()["articleFileFolder"]
    markedAsDeletedFile = atVoiceFolder + "/.config/_markedAsRead.rlst"
    markedAsDeletedText = open(markedAsDeletedFile).read().strip()
    markedAsDeletedFiles = markedAsDeletedText.split("\n:")[-1].split("\n")[1:]
    for file_path in markedAsDeletedFiles:
        if "articleUrls" in file_path:
            continue
        fileName = file_path.split("\t")[0].split("/")[-1]
        utils.hideFilesWithName(articleFileFolder, fileName)


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


def deleteDuplicateArticleFiles(urls_to_filenames):
    # Dictionary to store seen URLs in each directory
    dir_seen_urls = {}

    for fileName in urls_to_filenames:
        url = urls_to_filenames[fileName]
        url = utils.formatUrl(url)

        # Get directory of the file
        directory = os.path.dirname(fileName)

        if directory not in dir_seen_urls:
            # If directory is not in the dictionary, add it with the current url
            dir_seen_urls[directory] = {url}
        elif url in dir_seen_urls[directory] and url:
            # If url has been seen in this directory, delete the file
            print(fileName, url)
            os.remove(fileName)
        else:
            # If url has not been seen in this directory, add it to the set
            dir_seen_urls[directory].add(url)


def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    file_size = os.path.getsize(file_path)

    if file_size < 4096:
        with open(file_path, "rb") as f:
            hasher.update(f.read())
    else:
        offset = (file_size - 4096) // 2
        with open(file_path, "rb") as f:
            f.seek(offset)
            hasher.update(f.read(4096))

    return hasher.hexdigest()


def deleteDuplicateFiles(directory_path):
    duplicate_size_files = defaultdict(list)

    for root, _, filenames in os.walk(directory_path):
        if any(part.startswith(".") for part in root.split(os.sep)):
            continue

        for filename in filenames:
            full_path = os.path.join(root, filename)
            file_size = os.path.getsize(full_path)
            file_hash = calculate_file_hash(full_path)
            unique_key = f"{file_size}_{file_hash}_{root}"

            duplicate_size_files[unique_key].append(full_path)

    for unique_key, file_paths in duplicate_size_files.items():
        if len(file_paths) > 1:
            root_files = [
                path
                for path in file_paths
                if os.path.dirname(path).strip("/") == directory_path.strip("/")
            ]
            non_root_files = [
                path
                for path in file_paths
                if os.path.dirname(path).strip("/") != directory_path.strip("/")
            ]

            if root_files:
                files_to_remove = (
                    root_files[:-1] if len(non_root_files) == 0 else root_files
                )
            else:
                files_to_remove = non_root_files[:-1]
            print(
                "files_to_remove",
                files_to_remove,
                "root files",
                root_files,
                "non_root_files",
                non_root_files,
            )
            for file_path in files_to_remove:
                print("removed", file_path)
                os.remove(file_path)


if __name__ == "__main__":
    # import new documents and give them readable filenames
    reTitlePDFs.retitleAllPDFs()
    reTitlePDFs.moveDocsToTargetFolder()
    # update urlList files
    updateUrlListFiles(getConfig()["articleFileFolder"])
    # act on requests to delete/move/hide articles from atVoice app
    deleteFilesMarkedToDelete()
    moveFilesMarkedToMove()
    hideArticlesMarkedAsRead()
    markReadBookmarksAsRead()
    # delete duplicate files
    articlesAndUrls = utils.getUrlsInLists()
    deleteDuplicateArticleFiles(articlesAndUrls)
    deleteDuplicateFiles(getConfig()["articleFileFolder"])
    utils.addUrlToUrlFile(
        list(articlesAndUrls.values()),
        utils.getAbsPath("../storage/alreadyAddedArticles.txt"),
    )
    urlsToAdd = calcUrlsToAdd()
    generateUrlImportFilesForAtVoice(urlsToAdd)
