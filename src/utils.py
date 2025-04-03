import re
import hashlib
from io import StringIO, BytesIO
from ipfs_cid import cid_sha256_hash_chunked
from eldar import Query
from typing import Iterable
import glob
import urlexpander
from os import path
import json
from pathlib import Path
import os

# import snscrape.modules.twitter as sntwitter
# import snscrape
import pysnooper
import shutil
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


def delete_file_with_name(file_name, folder):
    # Find all files with the file name in the folder using our enhanced function
    # Delete all found files
    # print(f"Deleting {file_name} from {folder}")
    notFound = True
    possibleExts = ["pdf", "epub"]
    currentExt = file_name.split(".")[-1]
    possibleExts.append(currentExt)
    file_name = os.path.basename(file_name)
    for ext in possibleExts:
        try:
            fileName = file_name.split(".")[0] + "." + ext
            matching_file = os.path.join(folder, fileName)
            homeDir = os.path.expanduser("~")
            dest = os.path.join(homeDir, ".local/share/Trash/files/", file_name)
            if os.path.exists(matching_file):
                shutil.move(matching_file, dest)
                print(f"Deleted {matching_file}")
                notFound = False
        except OSError:
            pass
    if notFound:
        print(
            f"File {file_name} not found in folder {folder}, with extensions {possibleExts}"
        )


def hide_file_with_name(orgFileName, folder):
    possibleExts = ["pdf", "epub"]
    currentExt = orgFileName.split(".")[-1]
    orgFileName = os.path.basename(orgFileName)
    possibleExts.append(currentExt)
    notFound = True
    for ext in possibleExts:
        try:
            fileName = orgFileName.split(".")[0] + "." + ext
            matching_file = os.path.join(folder, fileName)
            if os.path.exists(matching_file):
                hiddenFileName = "." + fileName
                if hiddenFileName == "." or fileName[0] == ".":
                    continue
                hiddenFilePath = os.path.join(folder, hiddenFileName)
                print(f"HIDING {fileName} >> {hiddenFilePath}")
                shutil.move(matching_file, hiddenFilePath)
                notFound = False
                return hiddenFilePath
        except OSError:
            pass
    if notFound:
        print(
            f"File {orgFileName} not found in folder {folder}, with extensions {possibleExts}"
        )
    return orgFileName


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
    url = url.replace("###", "##")  # so that it isn't force refreshed in convertLinks
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
            try:
                hideFile(articleUrls[url].split("/")[-1])
            except OSError:
                print(f"Error hiding {articleUrls[url]}")
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


def getArticlesFromList(listName):
    """
    Returns a list of article filenames from the .rlst file named `listName`.
    If listName starts with '_', then any Syncthing conflict files are merged in
    (only their article lines) and subsequently removed.
    """

    config_path = getConfig()["atVoiceFolderPath"]
    listPath = os.path.join(config_path, ".config", listName + ".rlst")
    rootPath = os.path.join(getConfig()["droidEbooksFolderPath"])

    if not os.path.exists(listPath):
        return []

    def parse_article_lines(text):
        """
        Given the full text of a .rlst file, return (header_text, article_list).

        - header_text is the lines up to the last occurrence of a "\n:" marker
          (i.e., the "header" region). If no header is detected, returns None.
        - article_list is the list of extracted article filenames.
        """
        text = text.strip()
        if not text:
            return None, []

        lines = text.split("\n")

        # Detect a header if there's a second line that starts with ":"
        if len(lines) > 1 and lines[1].startswith(":"):
            # Everything up to the last "\n:" is considered the header
            parts = text.split("\n:")
            # All parts except the last are the header
            header_text = "\n:".join(parts[:-1]).rstrip("\n")
            # The last part is what comes after the final header marker
            tail = parts[-1].split("\n")
            # tail[0] is the ":" line, so skip it
            article_lines = tail[1:]
        else:
            # No header found
            header_text = None
            article_lines = lines

        # Extract article filenames from article_lines
        articles = []
        for line in article_lines:
            line = line.strip()
            if not line:
                continue
            # The first token (split by tab) holds the path
            parts = line.split("\t")
            if parts:
                if parts[0]:
                    filePathRelativeToRoot = os.path.relpath(parts[0], rootPath)
                    if filePathRelativeToRoot not in articles:
                        articles.append(filePathRelativeToRoot)

        return header_text, articles

    # -------------------------------------------------------
    # 1. Read and parse main file
    # -------------------------------------------------------
    with open(listPath, "r", encoding="utf-8") as f:
        mainText = f.read()

    mainHeader, mainArticles = parse_article_lines(mainText)

    # -------------------------------------------------------
    # 2. Check for conflict files only if listName starts with '_'
    # -------------------------------------------------------
    conflict_files = []
    if listName.startswith("_"):
        baseName = os.path.basename(listPath)
        dirName = os.path.dirname(listPath)
        pattern = baseName + ".sync-conflict-*"
        conflict_files = glob.glob(os.path.join(dirName, pattern))

    # -------------------------------------------------------
    # 3. Merge conflict articles (excluding their headers)
    # -------------------------------------------------------
    if conflict_files:
        print(f"Found {len(conflict_files)} conflict files for {listName}")
        for cfile in conflict_files:
            try:
                with open(cfile, "r", encoding="utf-8") as cf:
                    ctext = cf.read()
                # We only take the articles, ignoring conflict headers
                _, conflictArticles = parse_article_lines(ctext)
                for article in conflictArticles:
                    if article not in mainArticles:
                        mainArticles.append(article)
            except Exception as e:
                print(f"Error reading conflict file {cfile}: {e}")

        # -------------------------------------------------------
        # 4. Rewrite the main file with the merged articles
        # -------------------------------------------------------
        if mainHeader is not None:
            newText = f"{mainHeader}\n:\n" + "\n".join(mainArticles)
        else:
            articlesWithRoot = [
                os.path.join(rootPath, article) for article in mainArticles
            ]
            newText = "\n".join(articlesWithRoot)

        try:
            with open(listPath, "w", encoding="utf-8") as f:
                f.write(newText)

            # Delete the conflicts
            for cfile in conflict_files:
                try:
                    os.remove(cfile)
                except Exception as e:
                    print(f"Error deleting conflict file {cfile}: {e}")
        except Exception as e:
            print(f"Error saving merged content to {listPath}: {e}")

    # -------------------------------------------------------
    # 5. Return final article list
    # -------------------------------------------------------
    return mainArticles


def doesPathContainDotFolders(path):
    for folder in path.split("/")[:-1]:
        if folder and folder[0] == ".":
            return True
    return False


def getArticlePathsForQuery(
    query, formats=[], folderPath="", fileName=None, recursive=False, readState=None
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
    formats = formats if query == "*" else ["html", "mhtml"]  # important!
    fileNamesToSkip = getConfig()["fileNamesToSkip"]

    # Treat fileName as a format if provided, otherwise use provided formats
    search_targets = [glob.escape(fileName)] if fileName else formats
    # Create glob patterns for both root and recursive searches

    # Create the glob patterns
    glob_patterns = [
        *(
            (
                os.path.join(folderPath, globWildcard, f"{target}")
                if recursive
                else os.path.join(folderPath, f"{globWildcard}{target}")
            )
            for target in search_targets
        ),  # Recursively
    ]
    final_patterns = []
    for pattern in glob_patterns:
        lastSegment = path.split(pattern)[-1]
        if readState == "read":
            lastSegment = f".{lastSegment}"
        firstSegments = path.split(pattern)[:-1]
        pattern = os.path.join(*firstSegments, lastSegment)
        final_patterns.append(pattern)

    glob_patterns = final_patterns
    include_hidden = False if readState == "unread" else True
    allArticlesPaths = []
    for pattern in glob_patterns:
        try:
            matching_paths = glob.glob(
                pattern, recursive=recursive, include_hidden=include_hidden
            )
            matching_paths = [
                path for path in matching_paths if not doesPathContainDotFolders(path)
            ]
            allArticlesPaths.extend(matching_paths)
        except Exception as e:
            print(f"Error in glob pattern {pattern}: {e}")

    allArticlesPaths = [
        path
        for path in allArticlesPaths
        if not any(skip in path for skip in fileNamesToSkip)
    ]
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
    allArticlesPaths.extend(
        getArticlePathsForQuery(query, formats, path, readState=readState)
    )

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
        print(f"deleting disabled list: {listName}")
        os.remove(listPath)


def addArticlesToList(listName, articlePathsForList):
    listPath = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", listName + ".rlst"
    )
    createListIfNotExists(listPath)
    articleNamesInList = [line.split("/")[-1] for line in getArticlesFromList(listName)]
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

    articleList = newListText + existingArticleListText
    # remove duplicates from existingArticleListText, deleting articles at the top of the list first and while preserving the order
    deDupedArticleListText = []
    seen = set()
    for line in articleList.split("\n"):
        fileName = line.split("\t")[0].split("/")[-1].lower()
        if fileName not in seen:
            seen.add(fileName)
            deDupedArticleListText.append(line)
    articleList = "\n".join(deDupedArticleListText)

    combinedListText = headers + articleList
    if len(linesToAppend) > 0:
        print(
            "\n\n\n\nAdding the following articles to list: "
            + listName
            + "\n"
            + newListText
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
    if "\n:m" not in currentListText:
        # print(f":m not found in list {listName}")
        textWithArticlesRemoved = ""
    else:
        textWithArticlesRemoved = (
            "\n:m".join(currentListText.split("\n:m")[:-1])
            + "\n:m"
            + currentListText.split("\n:m")[-1].split("\n")[0]
            + "\n"
        )  # i.e. currentListText.split("\n:m")[-1].split("\n")[0] refers to the last line in the doc which starts with :m

    with open(listPath, "w") as f:
        f.write(textWithArticlesRemoved)


def getSrcUrlOfGitbook(articlePath):
    htmlText = open(articlePath, errors="ignore").read()
    if '" rel="nofollow">Original</a></p>' in htmlText:
        srcUrl = htmlText.split('" rel="nofollow">Link to original</a></p>')[0]
        srcUrl = srcUrl.split('><a href="')[-1]
        return srcUrl
    return None


def calculate_ipfs_hash(file_path):
    """Calculate IPFS hash for a file."""

    def as_chunks(stream: BytesIO, chunk_size: int) -> Iterable[bytes]:
        while len((chunk := stream.read(chunk_size))) > 0:
            yield chunk

    with open(file_path, "rb") as f:
        # Use a larger chunk size for better performance (64KB instead of 4 bytes)
        result = cid_sha256_hash_chunked(as_chunks(f, 65536))
        return result


def calculate_normal_hash(file_path):
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
