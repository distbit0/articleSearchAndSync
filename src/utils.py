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
    # Find all files with the file name in the folder using glob
    searchString = os.path.join(folder, "**", file_name)
    matching_files = glob.glob(searchString, recursive=True)

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
    # Find all files with the file name in the folder using glob
    searchString = os.path.join(folder, "**", file_name)
    matching_files = glob.glob(searchString, recursive=True)

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


def moveFilesWithNameToRootDir(folder, file_name):
    # Find all files with the file name in the folder using glob
    searchString = os.path.join(folder, "**", file_name)
    matching_files = glob.glob(searchString, recursive=True)

    # Move all found files to the root of the directory
    for f in matching_files:
        try:
            # Determine the new file path
            new_path = os.path.join(folder, os.path.basename(f))

            # # If file with the same name exists at the destination, we delete it before moving.
            # if os.path.isfile(new_path) and os.path.exists(f):
            #     print("deleted root file", new_path)
            # #     os.remove(new_path)
            # Move the file
            if f != new_path:
                shutil.move(f, new_path)
                print(f"Moved {f} to {new_path}")
        except OSError as e:
            print(f"Error moving {f}: {e}")


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
#         handle_cache(getAbsPath("./../storage/twitter_handles.json"), tweet_id, "")
#         return ""
#
#     # Access the 'user' attribute of the tweet, which is a User object,
#     # and then access the 'username' attribute of the User object
#     handle_cache(
#         getAbsPath("./../storage/twitter_handles.json"), tweet_id, tweet.user.username
#     )
#     return tweet.user.username
#


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
    listText = open(listPath).read().strip()
    if listText == "":
        return []
    if listText.split("\n")[1][0] == ":":
        listArticles = listText.split("\n:")[-1].split("\n")[1:]
    else:
        listArticles = listText.split("\n")
    articleFileNames = []
    for articleLine in listArticles:
        articleFileName = articleLine.split("\t")[0].split("/")[-1]
        articleFileNames.append(articleFileName)
    return articleFileNames


def doesPathContainDotFolders(path):
    for folder in path.split("/")[:-1]:
        if folder and folder[0] == ".":
            return True
    return False


def getArticlePathsForQuery(query, formats, folderPath="", fileName=None):
    folderPath = folderPath if folderPath else getConfig()["articleFileFolder"]
    folderPath = (folderPath + "/").replace("//", "/")
    formats = formats if query == "*" else ["html", "mhtml"]
    filePatterns = [folderPath + "**/*" + docFormat for docFormat in formats]
    print(filePatterns, query, folderPath)
    allArticlesPaths = []
    for pattern in filePatterns:
        articlePaths = list(glob.glob(pattern, recursive=True, include_hidden=True))
        articlePaths = [
            path for path in articlePaths if not doesPathContainDotFolders(path)
        ]
        allArticlesPaths.extend(articlePaths)

    fileNamesToSkip = getConfig()["fileNamesToSkip"]
    allArticlesPaths = [
        path
        for path in allArticlesPaths
        if not any(skip in path for skip in fileNamesToSkip)
    ]
    
    # Filter by fileName if provided
    if fileName:
        allArticlesPaths = [
            path for path in allArticlesPaths if fileName.lower() in os.path.basename(path).lower()
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
    allArticlesPaths.extend(getArticlePathsForQuery(query, formats, path))

    for articlePath in allArticlesPaths:
        skipBecauseReadState = False
        if readState:
            if readState == "read":
                isRead = originalArticlePath.split("/")[-1][0] == "."
                skipBecauseReadState = not isRead
            elif readState == "unread":
                isUnread = originalArticlePath.split("/")[-1][0] != "."
                skipBecauseReadState = not isUnread
        invalidSubject = not checkArticleSubject(originalArticlePath, subjects)

        if skipBecauseReadState or invalidSubject:
            continue

        matchInAricle = (
            True
            if query == "*"
            else searchFilter(open(articlePath, errors="ignore").read().strip())
        )

        if not matchInAricle:
            continue

        matchingArticles[originalArticlePath] = getUrlOfArticle(articlePath)

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
    newListText = "\n".join(linesToAppend) + "\n"
    currentListText = open(listPath).read().strip()
    headers, existingArticleListText = "", str(currentListText)
    if currentListText and currentListText.split("\n")[1][0] == ":":
        existingArticleListText = "\n".join(
            currentListText.split("\n:")[-1].split("\n")[1:]
        )
        headers = currentListText.replace(existingArticleListText, "").strip() + "\n"
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
