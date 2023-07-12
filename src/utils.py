import re
import glob
import urlexpander
from os import path
import json
from pathlib import Path
import os
import snscrape.modules.twitter as sntwitter
import snscrape
import shutil


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
            os.remove(f)
            print(f"Deleted {f}")
        except OSError as e:
            print(f"Error deleting {f}: {e}")


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
            shutil.move(f, new_path)
            print(f"Moved {f} to {new_path}")
        except OSError as e:
            print(f"Error moving {f}: {e}")


def makeDiscoursePrintable(url):
    if not url:
        return ""
    tempUrl = str(url)
    if tempUrl[-1] != "/":
        tempUrl += "/"
    if re.search("(\/t\/[^\/]*\/\d+\/)", tempUrl):
        # print(1, tempUrl)
        if re.search("(t\/[^\/]*\/\d+\/)$", tempUrl):
            tempUrl += "print"
            # print(2, tempUrl)
        if re.search("(t\/[^\/]*\/\d+\/)(([a-z]+|\d+)\/)$", tempUrl):
            tempUrl = re.sub(
                r"(t\/[^\/]*\/\d+\/)(([a-z]+|\d+)\/)$", r"\1print", tempUrl
            )
            # print(3, tempUrl)
    else:
        tempUrl = str(url)

        # print("\n\n\n")
    return tempUrl


def formatUrl(url):
    if "t.co/" in url:
        url = urlexpander.expand(url)
    url = url.replace("medium.com", "scribe.rip").strip()
    url = url.replace("en.m.wikipedia.org", "en.wikipedia.org").strip()
    url = re.sub(r"\?gi=.*", r"", url)
    url = re.sub(r"\&gi=.*", r"", url)
    return url


def getUrlOfArticle(articleFilePath):
    extractedUrl = ""
    with open(articleFilePath, errors="ignore") as _file:
        fileText = _file.read()
        urlPatterns = getConfig()["urlPatterns"]
        for urlPattern in urlPatterns:
            match = re.search(urlPattern, fileText)
            if match:
                extractedUrl = formatUrl(match.group(1).strip())
                break

        # if not extractedUrl:
        #     extractedUrl = articleFilePath

    return extractedUrl


def getUrlsInLists(subject=""):
    extractedUrls = {}
    articleFilePattern = getConfig()["articleFilePattern"]
    articleFileFolder = getConfig()["articleFileFolder"]
    articlePathPattern = articleFileFolder + articleFilePattern
    for f in glob.glob(articlePathPattern, recursive=True):
        articleSubject = str(f)
        if subject.lower() not in articleSubject.lower() and subject:
            continue
        extractedUrls[f] = getUrlOfArticle(f)
    return extractedUrls


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
    # Create a TwitterTweetScraper object for the given tweet_id
    username = handle_cache(getAbsPath("./../storage/twitter_handles.json"), tweet_id)
    if username != None:
        return username

    scraper = sntwitter.TwitterTweetScraper(tweet_id)

    # Use the get_items method to get the tweet
    try:
        for i, tweet in enumerate(scraper.get_items()):
            if i == 1:
                break
    except snscrape.base.ScraperException:
        handle_cache(getAbsPath("./../storage/twitter_handles.json"), tweet_id, "")
        return ""

    # Access the 'user' attribute of the tweet, which is a User object,
    # and then access the 'username' attribute of the User object
    handle_cache(
        getAbsPath("./../storage/twitter_handles.json"), tweet_id, tweet.user.username
    )
    return tweet.user.username


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

    return removeDupesPreserveOrder(blogUrls)


def getInvalidBlogSubstrings():
    invalidBlogSubstrings = getConfig()["invalidBlogSubstrings"]
    pdfFolders = getConfig()["pdfFolders"]
    pdfExcludedBlogs = []
    for folder in pdfFolders.values():
        pdfExcludedBlogs.append(getBlogFromUrl(folder["pdfBaseURL"]))
    invalidBlogSubstrings.extend(pdfExcludedBlogs)

    return invalidBlogSubstrings


def isValidBlog(url):
    validBlog = True
    invalidBlogSubstrings = getInvalidBlogSubstrings()
    for substring in invalidBlogSubstrings:
        if substring.lower() in url.lower():
            validBlog = False

    return validBlog


def mkdirAndParents(directory):
    Path(directory).mkdir(parents=True, exist_ok=True)


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))

    return fullPath


def getConfig():
    configFileName = getAbsPath("../config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())

    return config
