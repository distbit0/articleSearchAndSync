from ctypes import util
import sqlite3
import re
from pathlib import Path
import json
import utils
from utils import getConfig
import os
from collections import defaultdict
import reTitlePDFs
from generateLists import updateLists
from downloadNewArticles import downloadNewArticles
import sys
import shutil
import hashlib
from typing import Iterable
from io import BytesIO
from ipfs_cid import cid_sha256_hash_chunked
from articleSummary import summarize_articles, add_files_to_database
from articleTagging import main as tag_articles
import cProfile
import pstats

sys.path.append(getConfig()["convertLinksDir"])
from convertLinks import main as convertLinks


def calculate_ipfs_hash(file_path):
    def as_chunks(stream: BytesIO, chunk_size: int) -> Iterable[bytes]:
        while len((chunk := stream.read(chunk_size))) > 0:
            yield chunk

    with open(file_path, "rb") as f:
        result = cid_sha256_hash_chunked(as_chunks(f, 4))
        return result


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


def deleteFilesMarkedToDelete():
    markedAsDeletedFiles = utils.getArticlesFromList("_DELETE")
    articleFileFolder = getConfig()["articleFileFolder"]
    for fileName in markedAsDeletedFiles:
        utils.delete_files_with_name(articleFileFolder, fileName)
    utils.deleteAllArticlesInList("_DELETE")


def hideArticlesMarkedAsRead():
    markedAsReadFiles = utils.getArticlesFromList("_READ")
    articleFileFolder = getConfig()["articleFileFolder"]
    for fileName in markedAsReadFiles:
        if "articleUrls" in fileName:
            continue
        utils.hideFilesWithName(articleFileFolder, fileName)
    utils.deleteAllArticlesInList("_READ")


def updatePerTagFiles(root_folder):
    """Generate file lists per tag for both URLs and file names/hashes.

    This function queries the database for all tags, then for each tag:
    1. Creates a file containing the URLs of HTML/MHTML articles with that tag
    2. Creates a file containing names and hashes of all articles with that tag

    All files are stored in a single "tag_files" subdirectory.

    Args:
        root_folder: Path to the root folder where articles are stored
    """

    # Get the database path
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage",
        "article_summaries.db",
    )

    if not os.path.exists(db_path):
        print(f"Tag database not found at {db_path}")
        return

    # Create tag_files directory if it doesn't exist
    tag_files_dir = os.path.join(root_folder, "tag_files")
    os.makedirs(tag_files_dir, exist_ok=True)

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query all active tags
    cursor.execute(
        """
        SELECT id, name FROM tags 
        WHERE name NOT LIKE 'prev_folder_%'
        """
    )
    tags = cursor.fetchall()

    # Total number of tags processed
    total_tags = len(tags)
    tags_processed = 0

    # Process each tag
    for tag_id, tag_name in tags:
        tags_processed += 1
        print(f"Processing tag {tags_processed}/{total_tags}: {tag_name}")

        # Use searchArticlesByTags to get articles with this tag
        articles_with_tag = utils.searchArticlesByTags(
            any_tags=[tag_name], formats=[], path=root_folder, cursor=cursor
        )

        # Skip if no articles have this tag
        if not articles_with_tag:
            print(f"  - No articles found with tag '{tag_name}'")
            continue

        # Lists to store URLs and file data
        urls = []
        file_data = {}

        # Process each article
        for article_path, article_url in articles_with_tag.items():
            try:
                # Calculate hash for all files
                file_hash = calculate_ipfs_hash(article_path)
                file_data[article_path] = file_hash

                # Add URL if available
                if article_url:
                    urls.append(article_url)
            except Exception as e:
                print(f"Error processing {article_path}: {e}")

        # Sanitize tag name for file system
        safe_tag_name = re.sub(r"[^\w\-_\.]", "_", tag_name)

        # Write URL file if we found any URLs
        if urls:
            tag_url_file_path = os.path.join(tag_files_dir, f"{safe_tag_name}_urls.txt")

            with open(tag_url_file_path, "w") as f:
                for url in urls:
                    f.write(f"{url}\n")

            print(
                f"  - Created URL file with {len(urls)} URLs: {os.path.basename(tag_url_file_path)}"
            )

        # Write file data if we found any files
        if file_data:
            tag_file_path = os.path.join(
                tag_files_dir, f"{safe_tag_name}_files_and_hashes.json"
            )

            with open(tag_file_path, "w") as f:
                json.dump(file_data, f, indent=2)

            print(
                f"  - Created file hash data with {len(file_data)} files: {os.path.basename(tag_file_path)}"
            )

    conn.close()
    print(f"Finished processing {total_tags} tags")
    print(f"All tag files have been generated in: {tag_files_dir}")


def updatePerTagUrlListFiles(root_folder):
    """This function is deprecated. Use updatePerTagFiles() instead."""
    print(
        "WARNING: updatePerTagUrlListFiles is deprecated. Using updatePerTagFiles instead."
    )
    updatePerTagFiles(root_folder)


def updatePerTagFileNamesAndHashes(root_folder):
    """This function is deprecated. Use updatePerTagFiles() instead."""
    print(
        "WARNING: updatePerTagFileNamesAndHashes is deprecated. Using updatePerTagFiles instead."
    )
    updatePerTagFiles(root_folder)


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
        docPaths += utils.getArticlePathsForQuery(
            "*", docFormatsToMove, folderPath, recursive=False
        )

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
    # profiler = cProfile.Profile()
    # profiler.enable()

    print("download new articles")
    urlsToAdd = calcUrlsToAdd()
    urlsToAdd = urlsToAdd["AlreadyRead"] + urlsToAdd["UnRead"]
    downloadNewArticles(urlsToAdd)
    print("give files readable filenames")
    reTitlePDFs.retitleAllPDFs()
    print("add files to database")
    add_files_to_database()
    print("summarize articles")
    summarize_articles()
    print("tag articles")
    tag_articles()
    print("move docs to target folder")
    moveDocsToTargetFolder()
    print("update urlList files")
    updatePerTagFiles(getConfig()["articleFileFolder"])
    print("act on requests to delete/hide articles from atVoice app\n\n")
    print("delete files marked to delete")
    deleteFilesMarkedToDelete()
    print("hide articles marked as read")
    hideArticlesMarkedAsRead()
    print("mark read bookmarks as read")
    markReadBookmarksAsRead()
    print("add file hashes to already added files")
    addFileHashesToAlreadyAdded()
    print("add read file hashes to marked as read files")
    addReadFilesHashesToMarkedAsRead()
    print("delete duplicate files")
    articles = utils.searchArticlesForQuery(
        "*", [], readState="", formats=["html", "mhtml"]
    )
    articleUrls = [url for url in articles.values() if url]
    deleteDuplicateArticleFiles(articles)
    deleteDuplicateFiles(getConfig()["articleFileFolder"])
    print("update alreadyAddedArticles.txt")
    utils.addUrlToUrlFile(
        articleUrls,
        utils.getAbsPath("../storage/alreadyAddedArticles.txt"),
    )
    print("update @voice lists")
    updateLists()

    # profiler.disable()
    # stats = pstats.Stats(profiler)
    # stats.sort_stats(pstats.SortKey.CUMULATIVE)
    # stats.print_stats("src")
