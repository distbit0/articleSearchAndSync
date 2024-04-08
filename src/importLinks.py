from ctypes import util
import json
import utils
from utils import getConfig
import os
from collections import defaultdict
import reTitlePDFs
from generateLists import updateLists
import sys
import shutil
import hashlib

sys.path.append(getConfig()["convertLinksDir"])
from convertLinks import main as convertLinks


def getBookmarks():
    bookmarksFilePath = getConfig()["bookmarksFilePath"]
    with open(bookmarksFilePath) as f:
        bookmarks = json.load(f)
        return bookmarks


def addFileHashesToAlreadyAdded():
    articleFolder = getConfig()["articleFileFolder"]
    nonHtmlFormats = getConfig()["docFormatsToMove"]
    nonHtmlFormats = [fmt for fmt in nonHtmlFormats if fmt not in ["html", "mhtml"]]
    listFile = utils.getAbsPath("../storage/alreadyAddedArticles.txt")
    matchingArticles = utils.searchArticlesForQuery(
        "*", formats=nonHtmlFormats, path=articleFolder
    )
    alreadyAddedFileNames = str(utils.getUrlsFromFile(listFile)).lower()
    fileNames = [
        os.path.basename(filePath)
        for filePath in matchingArticles.keys()
        if os.path.basename(filePath) not in alreadyAddedFileNames
    ]
    fileHashes = [
        calculate_file_hash(filePath)
        for filePath in matchingArticles.keys()
        if os.path.basename(filePath) not in alreadyAddedFileNames
    ]
    itemsToAdd = list(set(fileNames + fileHashes))
    utils.addUrlToUrlFile(itemsToAdd, listFile)


def addReadFilesHashesToMarkedAsRead():
    articleFolder = getConfig()["articleFileFolder"]
    nonHtmlFormats = getConfig()["docFormatsToMove"]
    nonHtmlFormats = [fmt for fmt in nonHtmlFormats if fmt not in ["html", "mhtml"]]
    listFile = utils.getAbsPath("../storage/alreadyAddedArticles.txt")
    matchingArticles = utils.searchArticlesForQuery(
        "*", formats=nonHtmlFormats, path=articleFolder, readState="read"
    )
    alreadyMarkedAsReadFileNames = utils.getUrlsFromFile(listFile)
    fileNames = [
        os.path.basename(filePath)
        for filePath in matchingArticles.keys()
        if os.path.basename(filePath) not in alreadyMarkedAsReadFileNames
    ]
    fileHashes = [
        calculate_file_hash(filePath)
        for filePath in matchingArticles.keys()
        if os.path.basename(filePath) not in alreadyMarkedAsReadFileNames
    ]
    itemsToAdd = list(set(fileNames + fileHashes))
    utils.addUrlToUrlFile(itemsToAdd, listFile)

    fileHashes = [calculate_file_hash(filePath) for filePath in matchingArticles.keys()]
    utils.addUrlToUrlFile(fileHashes, listFile)


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


def calcUrlsToAdd(onlyRead=False):
    bookmarks = getBookmarks()
    urlsToAdd = {}

    if onlyRead:
        markedAsReadUrls = utils.getUrlsFromFile(
            utils.getAbsPath("../storage/markedAsReadArticles.txt")
        )

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
                    if onlyRead:
                        if (
                            url.lower() not in "\n".join(markedAsReadUrls).lower()
                            and url.lower() in "\n".join(allAddedUrls).lower()
                        ):
                            url = convertLinks(url, False, True)
                            if url and url[0]:
                                url = url[0]
                                if (
                                    url.lower()
                                    not in "\n".join(markedAsReadUrls).lower()
                                    and url.lower() in "\n".join(allAddedUrls).lower()
                                ):
                                    urlsToAdd[subject].append(url)
                                    print("added url: ", url)
                    else:
                        if url.lower() not in "\n".join(allAddedUrls).lower():
                            url = convertLinks(url, False, True)
                            if url and url[0]:
                                url = url[0]
                                if url.lower() not in "\n".join(allAddedUrls).lower():
                                    urlsToAdd[subject].append(url)
                                    print("added url: ", url)

    return urlsToAdd


def markReadBookmarksAsRead():
    readUrls = calcUrlsToAdd(onlyRead=True)["AlreadyRead"]
    utils.markArticlesWithUrlsAsRead(readUrls, getConfig()["articleFileFolder"])


def generateUrlImportFilesForAtVoice(urlsToAdd):
    atVoiceFolderPath = getConfig()["atVoiceFolderPath"]
    linkText = "\n".join(["\n".join(urlsToAdd[subject]) for subject in urlsToAdd])
    print(atVoiceFolderPath + "links" + ".txt")
    with open(os.path.join(atVoiceFolderPath, ".config", "links.txt"), "w") as f:
        f.write(linkText)


def moveFilesMarkedToMove():
    markedToMoveFiles = utils.getArticlesFromList("_MOVE")
    articleFileFolder = getConfig()["articleFileFolder"]
    for fileName in markedToMoveFiles:
        utils.moveFilesWithNameToRootDir(articleFileFolder, fileName)


def deleteFilesMarkedToDelete():
    markedAsDeletedFiles = utils.getArticlesFromList("_DELETE")
    articleFileFolder = getConfig()["articleFileFolder"]
    for fileName in markedAsDeletedFiles:
        utils.delete_files_with_name(articleFileFolder, fileName)


def hideArticlesMarkedAsRead():
    markedAsReadFiles = utils.getArticlesFromList("_READ")
    articleFileFolder = getConfig()["articleFileFolder"]
    for fileName in markedAsReadFiles:
        if "articleUrls" in fileName:
            continue
        utils.hideFilesWithName(articleFileFolder, fileName)


def updatePerFolderUrlListFiles(folder_path):
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
        if not url:
            continue
        url = utils.formatUrl(url)

        # Get directory of the file
        directory = os.path.dirname(fileName)

        if directory not in dir_seen_urls:
            # If directory is not in the dictionary, add it with the current url
            dir_seen_urls[directory] = {url}
        elif url in dir_seen_urls[directory] and url:
            # If url has been seen in this directory, delete the file
            print("deleting because duplicate", fileName, url)
            homeDir = os.path.expanduser("~")
            dest = os.path.join(
                homeDir, ".local/share/Trash/files/", fileName.split("/")[-1]
            )
            shutil.move(fileName, dest)
        else:
            # If url has not been seen in this directory, add it to the set
            dir_seen_urls[directory].add(url)


def moveDocsToTargetFolder():
    docPaths = []
    PDFFolders = getConfig()["pdfSourceFolders"]
    docFormatsToMove = getConfig()["docFormatsToMove"]
    targetFolder = getConfig()["articleFileFolder"]

    for folderPath in PDFFolders:
        docPaths += utils.getArticlePathsForQuery("*", docFormatsToMove, folderPath)

    print("LEN OF docPath", len(docPaths))

    alreadyAddedHashes = str(
        utils.getUrlsFromFile(utils.getAbsPath("../storage/alreadyAddedArticles.txt"))
    )
    markedAsReadHashes = str(
        utils.getUrlsFromFile(utils.getAbsPath("../storage/markedAsReadArticles.txt"))
    )

    for docPath in docPaths:
        docHash = calculate_file_hash(docPath)
        if docHash in alreadyAddedHashes:
            print("Skipping importing duplicate file:", docPath)
            docFileName = docPath.split("/")[-1]
            homeDir = os.path.expanduser("~")
            erroDocPath = os.path.join(
                homeDir, ".local/share/Trash/files/", "DUPLICATE_" + docFileName
            )
            shutil.move(docPath, erroDocPath)
            continue

        docName = docPath.split("/")[-1]

        # Create a unique filename if needed
        baseName, extension = os.path.splitext(docName)
        uniqueName = docName
        counter = 1
        while os.path.exists(os.path.join(targetFolder, uniqueName)):
            uniqueName = f"{baseName}_{counter}{extension}"
            counter += 1

        targetPath = os.path.join(targetFolder, uniqueName)

        if docHash in markedAsReadHashes:
            targetPath = os.path.join(targetFolder, "." + uniqueName)
            print("Marking as read:", docName)

        print("Moving", docName, "to", targetPath, "derived from", docPath)
        shutil.move(docPath, targetPath)

        utils.addUrlToUrlFile(
            [docHash, os.path.basename(targetPath)],
            utils.getAbsPath("../storage/alreadyAddedArticles.txt"),
        )


def deleteDuplicateFiles(directory_path):
    duplicate_size_files = defaultdict(list)

    for root, _, filenames in os.walk(directory_path):
        if any(part.startswith(".") for part in root.split(os.sep)):
            continue  ###why is this here... mightn't it result in duplicate hidden articles remaining?

        for filename in filenames:
            full_path = os.path.join(root, filename)
            file_size = os.path.getsize(full_path)
            file_hash = calculate_file_hash(full_path)
            unique_key = f"{file_size}_{file_hash}_{root}"

            duplicate_size_files[unique_key].append(full_path)

    for unique_key, file_paths in duplicate_size_files.items():
        if len(file_paths) > 1:
            filesMarkedAsRead = [
                path for path in file_paths if path.split("/")[-1][0] == "."
            ]
            if len(filesMarkedAsRead) < len(file_paths):
                for path in filesMarkedAsRead:
                    file_paths.remove(path)

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
                homeDir = os.path.expanduser("~")
                dest = os.path.join(
                    homeDir, ".local/share/Trash/files/", file_path.split("/")[-1]
                )
                shutil.move(file_path, dest)


if __name__ == "__main__":
    print("import new documents and give them readable filenames")
    reTitlePDFs.retitleAllPDFs()
    print("move docs to target folder")
    moveDocsToTargetFolder()
    print("update urlList files")
    updatePerFolderUrlListFiles(getConfig()["articleFileFolder"])
    print("act on requests to delete/move/hide articles from atVoice app\n\n")
    print("delete files marked to delete")
    deleteFilesMarkedToDelete()
    print("move files marked to move")
    moveFilesMarkedToMove()
    print("hide articles marked as read")
    hideArticlesMarkedAsRead()
    print("mark read bookmarks as read")
    markReadBookmarksAsRead()
    print("add file hashes to already added files")
    addFileHashesToAlreadyAdded()
    print("add read file hashes to marked as read files")
    addReadFilesHashesToMarkedAsRead()
    print("delete duplicate files")
    articles = utils.searchArticlesForQuery("*", [], readState="", formats=["html"])
    articleUrls = [url for url in articles.values() if url]
    deleteDuplicateArticleFiles(articles)
    deleteDuplicateFiles(getConfig()["articleFileFolder"])
    print("update alreadyAddedArticles.txt")
    utils.addUrlToUrlFile(
        articleUrls,
        utils.getAbsPath("../storage/alreadyAddedArticles.txt"),
    )
    print("update urls.txt")
    urlsToAdd = calcUrlsToAdd()
    generateUrlImportFilesForAtVoice(urlsToAdd)
    print("update @voice lists")
    updateLists()
