import re
from eldar import Query
import glob
import urlexpander
from os import path
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
    matching_file = os.path.join(folder, file_name)

    # Delete all found files
    try:
        homeDir = os.path.expanduser("~")
        dest = os.path.join(homeDir, ".local/share/Trash/files/", file_name)
        shutil.move(matching_file, dest)
        print(f"Deleted {matching_file}")
    except OSError as e:
        print(f"Error deleting {matching_file}: {e}")


def hideFilesWithName(folder, file_name):
    # Find all files with the file name in the folder using our enhanced function
    matching_file = os.path.join(folder, file_name)

    # Hide all found files
    hideFile(matching_file)


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

    # Read the main list file content
    listText = open(listPath).read().strip()

    # Only process conflict files if the list name starts with an underscore
    has_conflicts = False
    if listName.startswith("_"):
        # Find and process Syncthing conflict files
        baseName = os.path.basename(listPath)
        dirName = os.path.dirname(listPath)
        conflict_pattern = f"{baseName}.sync-conflict-*"
        conflict_files = glob.glob(os.path.join(dirName, conflict_pattern))

        if conflict_files:
            has_conflicts = True
            # Read all conflict files content
            for conflict_file in conflict_files:
                try:
                    conflict_text = open(conflict_file).read().strip()
                    if conflict_text:
                        # Append conflict content to main content
                        if listText:
                            listText += "\n" + conflict_text
                        else:
                            listText = conflict_text
                except Exception as e:
                    print(f"Error reading conflict file {conflict_file}: {e}")

    # If list text is still empty after adding conflict files, return empty list
    if not listText:
        return []

    # Split the text into lines
    lines = listText.split("\n")

    # Make sure we have at least 2 lines before checking index 1
    if len(lines) > 1 and lines[1].startswith(":"):
        listArticles = listText.split("\n:")[-1].split("\n")[1:]
    else:
        # Simple format with no headers
        listArticles = lines

    # Process article file names, removing duplicates
    articleFileNames = []
    for articleLine in listArticles:
        if not articleLine.strip():  # Skip empty lines
            continue

        parts = articleLine.split("\t")
        if parts:
            path_parts = parts[0].split("/")
            if path_parts:
                articleFileName = path_parts[-1]
                if articleFileName not in articleFileNames:
                    articleFileNames.append(articleFileName)

    # If we found conflict files, save the merged content back to the main file
    # and delete the conflict files
    if has_conflicts:
        try:
            # Save the merged content
            with open(listPath, "w") as f:
                f.write(listText)

            # Delete the conflict files
            for conflict_file in conflict_files:
                try:
                    os.remove(conflict_file)
                except Exception as e:
                    print(f"Error deleting conflict file {conflict_file}: {e}")
        except Exception as e:
            print(f"Error saving merged content to {listPath}: {e}")

    return articleFileNames


def doesPathContainDotFolders(path):
    for folder in path.split("/")[:-1]:
        if folder and folder[0] == ".":
            return True
    return False


def getArticlePathsForQuery(
    query, formats=[], folderPath="", fileName=None, recursive=True, readState=None
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

    # Determine file prefix pattern based on read state
    file_prefix = ""
    if readState == "read":
        file_prefix = "."  # For read files (dot files)
    elif readState == "unread":
        file_prefix = "[^.]"  # For unread files (non-dot files)
    # Default is empty string - no additional prefix needed

    # Create the glob patterns using the determined prefix
    glob_patterns = [
        *(
            os.path.join(folderPath, globWildcard, f"{file_prefix}*{target}")
            for target in search_targets
        ),  # Recursively
    ]
    allArticlesPaths = []
    for pattern in glob_patterns:
        try:
            matching_paths = glob.glob(
                pattern, recursive=recursive, include_hidden=True
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


def searchArticlesByTags(
    all_tags=[], any_tags=[], readState="", formats=[], cursor=None
):
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
    # Early return conditions
    is_format_specific = (
        formats and len(formats) > 0 and formats != getConfig()["docFormatsToMove"]
    )
    if not all_tags and not any_tags and not is_format_specific:
        return {}

    # Get database path
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage",
        "article_summaries.db",
    )
    if not os.path.exists(db_path):
        print(f"Tag database not found at {db_path}")
        return {}

    # Get all article paths that match the format criteria
    article_paths = getArticlePathsForQuery("*", formats)

    # If no tags specified and only filtering by format, just apply read state filter and return
    if not all_tags and not any_tags:
        matchingArticles = {}
        for articlePath in article_paths:
            if _should_include_by_read_state(articlePath, readState):
                matchingArticles[articlePath] = getUrlOfArticle(articlePath)
        return matchingArticles

    # Create DB connection if not provided
    close_conn = False
    if not cursor:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        close_conn = True

    try:
        # Extract filenames from paths for efficient filtering
        filenames = {os.path.basename(path): path for path in article_paths}

        # Build SQL query for tag filtering
        query_params = []

        # Base SQL query to get article summaries
        sql = """
        SELECT as1.file_name, as1.id 
        FROM article_summaries as1
        WHERE as1.file_name IN ({})
        """.format(
            ",".join(["?"] * len(filenames))
        )

        query_params.extend(filenames.keys())

        # Filter by all_tags (AND logic)
        if all_tags:
            # For each required tag, join to article_tags and check for match
            for i, tag in enumerate(all_tags):
                tag_alias = f"at{i}"
                tag_join = f"""
                JOIN article_tags {tag_alias} ON as1.id = {tag_alias}.article_id
                JOIN tags t{i} ON {tag_alias}.tag_id = t{i}.id AND t{i}.name = ? AND {tag_alias}.matches = 1
                """
                sql = sql.replace(
                    "FROM article_summaries as1",
                    f"FROM article_summaries as1 {tag_join}",
                )
                query_params.append(tag)

        # Filter by any_tags (OR logic)
        if any_tags:
            or_conditions = []
            for tag in any_tags:
                or_conditions.append("(t_any.name = ? AND at_any.matches = 1)")
                query_params.append(tag)

            if or_conditions:
                any_tag_join = """
                JOIN article_tags at_any ON as1.id = at_any.article_id
                JOIN tags t_any ON at_any.tag_id = t_any.id
                """
                any_tag_where = " AND (" + " OR ".join(or_conditions) + ")"

                # Add the join to the FROM clause
                sql = sql.replace(
                    "FROM article_summaries as1",
                    f"FROM article_summaries as1 {any_tag_join}",
                )
                # Add the OR conditions to the WHERE clause
                sql += any_tag_where

        # Execute query
        cursor.execute(sql, query_params)
        matching_files = cursor.fetchall()

        # Build result dictionary
        matchingArticles = {}
        for filename, _ in matching_files:
            if filename in filenames:
                article_path = filenames[filename]
                if _should_include_by_read_state(article_path, readState):
                    matchingArticles[article_path] = getUrlOfArticle(article_path)

        return matchingArticles

    finally:
        if close_conn and cursor:
            cursor.connection.close()


def _should_include_by_read_state(article_path, readState):
    """Helper function to check if an article should be included based on read state"""
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
