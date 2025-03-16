import re
from unittest import skip
from eldar import Query
import glob
from matplotlib import lines
import urlexpander
from os import path, read
import json
from pathlib import Path
import os
import sqlite3

# import snscrape.modules.twitter as sntwitter
# import snscrape
import pysnooper
import shutil
import PyPDF2
import traceback


def checkArticleSubject(articlePath, subjects):
    if not subjects:
        return True
    # articlePath = "/".join(articlePath.split("/")[:-1]) commented out because sometimes I want to filter by the filename e.g. to find yt videos
    for subject in subjects:
        if subject.lower() in articlePath.lower():
            return True
    return False


def handle_cache(file_name, key, value=None):
    # Load existing cache or initialize an empty cache if the file does not exist
    cache = {}
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            cache = json.load(f)

    if value is None:
        # Get the value from cache
        return cache.get(key)
    else:
        # Write value to cache
        cache[key] = value
        with open(file_name, "w") as f:
            json.dump(cache, f)


def delete_files_with_name(folder, file_name):
    # Find all files with the file name in the folder using our enhanced function
    matching_files = getArticlePathsForQuery("*", [], folder, file_name)

    # Delete all found files
    for f in matching_files:
        try:
            homeDir = os.path.expanduser("~")
            dest = os.path.join(homeDir, ".local/share/Trash/files/", f.split("/")[-1])
            shutil.move(f, dest)
            print(f"Deleted {f}")
        except OSError as e:
            print(f"Error deleting {f}: {e}")


def hideFilesWithName(folder, file_name):
    # Find all files with the file name in the folder using our enhanced function
    matching_files = getArticlePathsForQuery("*", [], folder, file_name)

    # Hide all found files
    for f in matching_files:
        hideFile(f)


def hideFile(f):
    fileName = f.split("/")[-1]
    hiddenFileName = "." + fileName
    if hiddenFileName == "." or fileName[0] == ".":
        return
    hiddenFilePath = f.split("/")[:-1]
    hiddenFilePath.append(hiddenFileName)
    hiddenFilePath = "/".join(hiddenFilePath)
    print("HIDING", f, "  >>  ", hiddenFilePath)
    try:
        shutil.move(f, hiddenFilePath)
    except OSError as e:
        print(f"Error hiding {f}: {e}")


def formatUrl(url):
    if "t.co/" in url:
        url = urlexpander.expand(url)
    url = url.replace("medium.com", "scribe.rip").strip()
    url = url.replace("en.m.wikipedia.org", "en.wikipedia.org").strip()
    if "gist.github.com" in url:
        usernameIsInUrl = len(url.split("/")) > 4
        if usernameIsInUrl:
            url = "https://gist.github.com/" + url.split("/")[-1]

    url = re.sub(r"\?gi=.*", r"", url)
    url = re.sub(r"\&gi=.*", r"", url)
    if "discord.com" in url:
        url = url.replace("#update", "")
    return url


def getUrlOfArticle(articleFilePath):
    extractedUrl = ""
    articleExtension = articleFilePath.split(".")[-1].lower()

    if articleExtension not in ["txt", "html", "mhtml"]:
        return ""

    with open(articleFilePath, errors="ignore") as _file:
        fileText = _file.read()
        urlPatterns = getConfig()["urlPatterns"]
        for urlPattern in urlPatterns:
            match = re.search(urlPattern, fileText)
            if match:
                extractedUrl = formatUrl(match.group(1).strip())
                break

    return extractedUrl


def markArticlesWithUrlsAsRead(readUrls, articleFolder):
    articleUrls = searchArticlesForQuery("*", [], "", ["html", "mhtml"])
    articleUrls = {v: k for k, v in articleUrls.items()}
    for url in readUrls:
        if url in articleUrls:
            hideFile(articleUrls[url])
        addUrlToUrlFile(url, getAbsPath("./../storage/markedAsReadArticles.txt"))


def getUrlsFromFile(urlFile):
    allUrls = []
    with open(urlFile, "r") as allUrlsFile:
        fileText = allUrlsFile.read().strip()
        for url in fileText.strip().split("\n"):
            url = formatUrl(url)
            allUrls.append(url)
    return allUrls


def removeDupesPreserveOrder(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def addUrlToUrlFile(urlOrUrls, urlFile, overwrite=False):
    mode = "w" if overwrite else "a"
    with open(urlFile, mode) as allUrlsFile:
        if type(urlOrUrls) == type([]):
            for url in urlOrUrls:
                url = formatUrl(url)
                allUrlsFile.write(url + "\n")
        else:
            urlOrUrls = formatUrl(urlOrUrls)
            allUrlsFile.write(urlOrUrls + "\n")

    removeDupeUrlsInFile(urlFile)


def removeDupeUrlsInFile(urlFile):
    urls = getUrlsFromFile(urlFile)
    uniqueUrls = removeDupesPreserveOrder(urls)
    with open(urlFile, "w") as allUrlsFile:
        for url in uniqueUrls:
            allUrlsFile.write(url + "\n")


def getTwitterAccountFromTweet(tweet_id):
    return "NO USERNAME FOUND"


#     # Create a TwitterTweetScraper object for the given tweet_id
#     username = handle_cache(getAbsPath("./../storage/twitter_handles.json"), tweet_id)
#     if username != None:
#         return username
#
#     scraper = sntwitter.TwitterTweetScraper(tweet_id)
#
#     # Use the get_items method to get the tweet
#     try:
#         for i, tweet in enumerate(scraper.get_items()):
#             if i == 1:
#                 break
#     except snscrape.base.ScraperException:
#         handle_cache(
#             getAbsPath("./../storage/twitter_handles.json"), tweet_id, ""
#         )
#         return ""
#
#     # Access the 'user' attribute of the tweet, which is a User object,
#     # and then access the 'username' attribute of the User object
#     handle_cache(
#         getAbsPath("./../storage/twitter_handles.json"), tweet_id, tweet.user.username
#     )
#     return tweet.user.username


def getBlogFromUrl(url):
    url = url.replace("nitter.net", "twitter.com")
    if "https://scribe.rip" in url and url.count("/") < 4:
        pass
    if "gist.github.com" in url:
        matches = re.search(r"(https:\/\/gist.github.com\/.*)\/", url)
    elif "https://scribe.rip" in url:
        matches = re.search(r"(https:\/\/scribe.rip\/[^\/]*)\/", url)
    elif "https://medium.com" in url:
        matches = re.search(r"(https:\/\/medium.com\/[^\/]*)\/", url)
    elif ".scribe.rip" in url:
        matches = re.search(r"(https:\/\/.*\.scribe.rip\/)", url)
    elif ".medium.com" in url:
        matches = re.search(r"(https:\/\/.*\.medium.com\/)", url)
    elif "https://mirror.xyz" in url:
        matches = re.search(r"(https:\/\/mirror.xyz\/.*?)\/", url)
    elif "https://write.as" in url:
        matches = re.search(r"(https:\/\/write.as\/.*?)\/", url)
    elif "twitter.com" in url and "/status/" in url:
        url = url.strip("/")
        matches = re.search(r"(https:\/\/twitter.com\/.*?)\/status\/.*", url)
    elif "twitter.com" in url and "/status/" not in url:
        url = url.strip("/")
        matches = re.search(r"(https:\/\/twitter.com\/.*)", url)
    elif "https://threadreaderapp" in url:
        matches = re.search(r"(.*)", "")
        url = url.strip("/").replace(".html", "")
        tweetId = re.search(r"https:\/\/threadreaderapp.com\/thread\/(.*)", url)
        if tweetId.group(1):
            twitterAccount = getTwitterAccountFromTweet(tweetId.group(1))
            if twitterAccount:
                twitterAccountUrl = "https://twitter.com/" + twitterAccount
                matches = re.search(r"(.*)", twitterAccountUrl)
    else:
        matches = re.search(r"^(http[s]*:\/\/[^\/]+)", url)

    if matches:
        blog = matches.group(1).strip()
    else:
        blog = url
    blog = blog.rstrip("/")

    return blog


def getBlogsFromUrls(urls):
    blogUrls = []
    for url in urls:
        if isValidBlog(url):
            blogUrl = getBlogFromUrl(url)
            if blogUrl:
                blogUrls.append(blogUrl)

    return blogUrls


def getInvalidBlogSubstrings():
    invalidBlogSubstrings = getConfig()["invalidBlogSubstrings"]
    return invalidBlogSubstrings


def isValidBlog(url):
    validBlog = True
    invalidBlogSubstrings = getInvalidBlogSubstrings()
    for substring in invalidBlogSubstrings:
        if substring.lower() in url.lower():
            validBlog = False

    if not url.startswith("http"):
        validBlog = False

    return validBlog


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))

    return fullPath


def getConfig():
    configFileName = getAbsPath("../config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config


def getPdfText(pdf, pages=None):
    pdfText = []
    try:
        pdfFileObj = open(pdf, "rb")
        pdfReader = PyPDF2.PdfReader(pdfFileObj)
        pages = len(pdfReader.pages) if not pages else min(pages, len(pdfReader.pages))
        for pageNumber in range(pages):
            pageObj = pdfReader.pages[pageNumber]
            pdfText.append(pageObj.extract_text())
        pdfFileObj.close()
    except PyPDF2.errors.PdfReadError:
        traceback.print_exc()
        print("Error in pdf: ", pdf)
        return None
    pdfText = "\n".join(pdfText)
    return pdfText


def getArticlesFromList(listName):
    listPath = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", listName + ".rlst"
    )

    # Check if file exists
    if not os.path.exists(listPath):
        return []

    listText = open(listPath).read().strip()
    if listText == "":
        return []

    # Split the text into lines
    lines = listText.split("\n")

    # Make sure we have at least 2 lines before checking index 1
    if len(lines) > 1 and lines[1].startswith(":"):
        listArticles = listText.split("\n:")[-1].split("\n")[1:]
    else:
        # Simple format with no headers
        listArticles = lines

    articleFileNames = []
    for articleLine in listArticles:
        if not articleLine.strip():  # Skip empty lines
            continue

        parts = articleLine.split("\t")
        if parts:
            path_parts = parts[0].split("/")
            if path_parts:
                articleFileName = path_parts[-1]
                articleFileNames.append(articleFileName)

    return articleFileNames


def doesPathContainDotFolders(path):
    for folder in path.split("/")[:-1]:
        if folder and folder[0] == ".":
            return True
    return False


def getArticlePathsForQuery(
    query, formats, folderPath="", fileName=None, recursive=True
):
    """
    Get article paths matching the query, formats, and optional fileName.

    Args:
        query: Query to match against article paths (set to "*" for all articles)
        formats: List of file formats to include
        folderPath: Path to search in (default: from config)
        fileName: Optional specific filename to search for

    Returns:
        List of article paths matching the criteria
    """
    globWildcard = "**" if recursive else "*"
    folderPath = folderPath if folderPath else getConfig()["articleFileFolder"]
    folderPath = (folderPath + "/").replace("//", "/")
    formats = getConfig()["docFormatsToMove"] if not formats else formats
    formats = formats if query == "*" else ["html", "mhtml"]
    fileNamesToSkip = getConfig()["fileNamesToSkip"]

    # Determine the glob pattern based on whether we're searching for a specific file
    glob_patterns = []

    if fileName:
        # Use glob.escape to properly escape special characters in the filename
        escaped_file_name = glob.escape(fileName)

        # Create a pattern to search for this specific file
        glob_patterns = [os.path.join(folderPath, globWildcard, escaped_file_name)]
    else:
        # Original implementation for when no specific fileName is provided
        glob_patterns = [
            os.path.join(folderPath, globWildcard, f"*{docFormat}")
            for docFormat in formats
        ]

    # Use a single approach to search using glob
    allArticlesPaths = []
    for pattern in glob_patterns:
        try:
            matching_paths = glob.glob(pattern, recursive=recursive)
            # Filter out dot folders
            matching_paths = [
                path for path in matching_paths if not doesPathContainDotFolders(path)
            ]
            allArticlesPaths.extend(matching_paths)
        except Exception as e:
            print(f"Error in glob pattern {pattern}: {e}")

    # Filter out files to skip
    allArticlesPaths = [
        path
        for path in allArticlesPaths
        if not any(skip in path for skip in fileNamesToSkip)
    ]

    # Remove duplicates
    allArticlesPaths = list(set(allArticlesPaths))
    return allArticlesPaths


def searchArticlesForQuery(query, subjects=[], readState="", formats=[], path=""):
    searchFilter = Query(query, ignore_case=True, match_word=False, ignore_accent=False)
    matchingArticles = {}
    allArticlesPaths = []
    if (
        "pdf" in formats and query != "*" and path == ""
    ):  # i.e. if we want to search in the text of the pdf files
        formats.remove("pdf")
    allArticlesPaths.extend(getArticlePathsForQuery(query, formats, path))

    for articlePath in allArticlesPaths:
        skipBecauseReadState = False
        if readState:
            if readState == "read":
                isRead = articlePath.split("/")[-1][0] == "."
                skipBecauseReadState = not isRead
            elif readState == "unread":
                isUnread = articlePath.split("/")[-1][0] != "."
                skipBecauseReadState = not isUnread
        invalidSubject = not checkArticleSubject(articlePath, subjects)

        if skipBecauseReadState or invalidSubject:
            continue

        matchInAricle = (
            True
            if query == "*"
            else searchFilter(open(articlePath, errors="ignore").read().strip())
        )

        if not matchInAricle:
            continue

        matchingArticles[articlePath] = getUrlOfArticle(articlePath)

    return matchingArticles


def createListIfNotExists(listPath):
    exists = os.path.exists(listPath)
    if not exists:
        open(listPath, "a").close()
    return True


def deleteListIfExists(listName):
    listPath = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", listName + ".rlst"
    )
    if os.path.exists(listPath):
        print("deleting disabled list: ", listName)
        os.remove(listPath)


def addArticlesToList(listName, articlePathsForList):
    listPath = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", listName + ".rlst"
    )
    createListIfNotExists(listPath)
    articleNamesInList = getArticlesFromList(listName)
    droidEbooksFolderPath = getConfig()["droidEbooksFolderPath"]
    articleFileFolder = getConfig()["articleFileFolder"]
    linesToAppend = []
    for articlePath in articlePathsForList:
        articleName = articlePath.split("/")[-1]
        relativeArticlePath = os.path.relpath(articlePath, articleFileFolder)
        droidArticlePath = os.path.join(droidEbooksFolderPath, relativeArticlePath)
        if articleName not in articleNamesInList:
            displayName = articleName.split(".")[0]
            linesToAppend.append(droidArticlePath + "\t" + displayName)
    newListText = "\n".join(linesToAppend) + "\n" if linesToAppend else ""

    # Read the current list content safely
    currentListText = ""
    if os.path.exists(listPath):
        with open(listPath, "r") as f:
            currentListText = f.read().strip()

    headers, existingArticleListText = "", ""

    # Handle list format safely, checking for sufficient lines and format
    if currentListText:
        lines = currentListText.split("\n")
        # Check if we have at least 2 lines and the second line starts with ":"
        if len(lines) > 1 and lines[1].startswith(":"):
            existingArticleListText = "\n".join(
                currentListText.split("\n:")[-1].split("\n")[1:]
            )
            headers = (
                currentListText.replace(existingArticleListText, "").strip() + "\n"
            )
        else:
            # Simple format with no headers
            existingArticleListText = currentListText

    combinedListText = headers + newListText + existingArticleListText

    print(
        "\n\n\n\nAdding the following articles to list: " + listName,
        "\n",
        newListText,
    )

    if len(linesToAppend) > 0:
        with open(listPath, "w") as f:
            f.write(combinedListText)


def deleteAllArticlesInList(listName):
    listPath = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", listName + ".rlst"
    )
    createListIfNotExists(listPath)
    currentListText = open(listPath).read().strip()

    textWithArticlesRemoved = ""
    if ":m" not in currentListText:
        textWithArticlesRemoved = ""
    else:
        textWithArticlesRemoved = (
            "\n".join(currentListText.split(":m")[:-1])
            + "\n"
            + currentListText.split(":m")[-1].split("\n")[0]
        )

    with open(listPath, "w") as f:
        print("about to write: ", textWithArticlesRemoved)
        # f.write(textWithArticlesRemoved)


def getSrcUrlOfGitbook(articlePath):
    htmlText = open(articlePath, errors="ignore").read()
    if '" rel="nofollow">Original</a></p>' in htmlText:
        srcUrl = htmlText.split('" rel="nofollow">Link to original</a></p>')[0]
        srcUrl = srcUrl.split('><a href="')[-1]
        return srcUrl
    return None


def searchArticlesByTags(all_tags=[], any_tags=[], readState="", formats=[], path=""):
    """
    Search for articles that match specified tags.

    Args:
        all_tags: List of tags where all must match (AND logic)
        any_tags: List of tags where any must match (OR logic)
        readState: Filter by read state ('read', 'unread', or '') - empty string means no filtering
        formats: List of file formats to include
        path: Base path to search in

    Returns:
        Dict of article paths with their URLs
    """
    # Connect to the database first to avoid processing unnecessary files
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage",
        "article_summaries.db",
    )
    if not os.path.exists(db_path):
        print(f"Tag database not found at {db_path}")
        return {}

    # Special case: If both all_tags and any_tags are empty, but we're not filtering by format only,
    # this is likely a misconfiguration. Return an empty result to avoid returning all files.
    is_format_specific = (
        formats and len(formats) > 0 and formats != getConfig()["docFormatsToMove"]
    )
    if not all_tags and not any_tags and not is_format_specific:
        return {}

    # Get all articles matching the format criteria - don't filter by filename prefix yet
    # so we can find all possible articles first
    matchingArticles = {}
    allArticlesPaths = []
    if (
        "pdf" in formats and path == ""
    ):  # i.e. if we want to search in the text of the pdf files
        formats.remove("pdf")
    allArticlesPaths.extend(getArticlePathsForQuery("*", formats, path))

    # Helper function to check if an article should be included based on read state
    def should_include_by_read_state(article_path):
        # If no read state filter, include all articles
        if not readState:
            return True

        filename = os.path.basename(article_path)
        is_read = filename[0] == "."

        if readState == "read":
            return is_read
        elif readState == "unread":
            return not is_read

        return True

    # If only filtering by format (no tags), apply read state filter and return
    if not all_tags and not any_tags:
        for articlePath in allArticlesPaths:
            if should_include_by_read_state(articlePath):
                matchingArticles[articlePath] = getUrlOfArticle(articlePath)
        return matchingArticles

    # Open DB connection for tag filtering
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Collect tag IDs to avoid repeated lookups
    tag_id_mapping = {}
    if all_tags or any_tags:
        tags_to_check = list(set(all_tags + any_tags))  # Combine and deduplicate

        for tag in tags_to_check:
            cursor.execute("SELECT id FROM tags WHERE name = ?", (tag,))
            tag_id_result = cursor.fetchone()

            if tag_id_result:
                tag_id_mapping[tag] = tag_id_result[0]

    # If we're using tag filtering and none of the requested tags exist in the database,
    # return an empty result to avoid unnecessary processing
    if (all_tags or any_tags) and not tag_id_mapping:
        conn.close()
        return {}

    # Get a list of all articles in the database to filter paths efficiently
    cursor.execute("SELECT file_name FROM article_summaries")
    db_articles = {
        row[0]: None for row in cursor.fetchall()
    }  # Use dict for faster lookups

    # Process each article path
    for articlePath in allArticlesPaths:
        # Skip based on read state
        if not should_include_by_read_state(articlePath):
            continue

        # Skip if not in database
        filename = os.path.basename(articlePath)
        if filename not in db_articles:
            continue

        # Get article ID
        cursor.execute(
            "SELECT id FROM article_summaries WHERE file_name = ?", (filename,)
        )
        article_id_result = cursor.fetchone()
        if not article_id_result:
            continue

        article_id = article_id_result[0]

        # Check if article matches all required tags (AND logic)
        matches_all = True
        if all_tags:
            for tag in all_tags:
                tag_id = tag_id_mapping.get(tag)
                if not tag_id:
                    matches_all = False
                    break

                # Check if article has this tag
                cursor.execute(
                    "SELECT matches FROM article_tags WHERE article_id = ? AND tag_id = ?",
                    (article_id, tag_id),
                )
                tag_match = cursor.fetchone()

                if not tag_match or not tag_match[0]:
                    matches_all = False
                    break

        if not matches_all:
            continue

        # Check if article matches any of the "any" tags (OR logic)
        matches_any = len(any_tags) == 0  # True if no any_tags (no requirement)
        if any_tags and not matches_any:
            for tag in any_tags:
                tag_id = tag_id_mapping.get(tag)
                if not tag_id:
                    continue

                # Check if article has this tag
                cursor.execute(
                    "SELECT matches FROM article_tags WHERE article_id = ? AND tag_id = ?",
                    (article_id, tag_id),
                )
                tag_match = cursor.fetchone()

                if tag_match and tag_match[0]:
                    matches_any = True
                    break

        # Include article if it passes both all_tags and any_tags filters
        if matches_all and matches_any:
            matchingArticles[articlePath] = getUrlOfArticle(articlePath)

    conn.close()
    return matchingArticles
