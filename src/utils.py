import re
import glob
import urlexpander
from os import path
import json
from pathlib import Path
import os


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
    extractedUrls = []
    articleFilePattern = getConfig()["articleFilePattern"]
    articleFileFolder = getConfig()["articleFileFolder"]
    articlePathPattern = articleFileFolder + articleFilePattern
    for f in glob.glob(articlePathPattern, recursive=True):
        articleSubject = str(f)
        if subject.lower() not in articleSubject.lower() and subject:
            continue
        extractedUrls.append(getUrlOfArticle(f))
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


def addUrlToUrlFile(urlsOrUrls, urlFile, overwrite=False):
    mode = "w" if overwrite else "a"
    with open(urlFile, mode) as allUrlsFile:
        if type(urlsOrUrls) == type([]):
            for url in urlsOrUrls:
                url = formatUrl(url)
                allUrlsFile.write(url + "\n")
        else:
            urlsOrUrls = formatUrl(urlsOrUrls)
            allUrlsFile.write(urlsOrUrls + "\n")

    removeDupeUrlsInFile(urlFile)


def removeDupeUrlsInFile(urlFile):
    urls = getUrlsFromFile(urlFile)
    uniqueUrls = removeDupesPreserveOrder(urls)
    with open(urlFile, "w") as allUrlsFile:
        for url in uniqueUrls:
            allUrlsFile.write(url + "\n")


def getBlogFromUrl(url):
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
        matches = re.search(r"(https:\/\/mirror.xyz\/.*?)\/", url + "/")
    elif "https://write.as" in url:
        matches = re.search(r"(https:\/\/write.as\/.*?)\/", url + "/")
    else:
        matches = re.search(r"^(?:http[s]*://[^\/]+)", url)

    if matches:
        blog = matches.group(0).strip()
    else:
        blog = url
    blog = blog.rstrip("/")

    return blog


def getBlogsFromUrls(urls):
    blogUrls = []
    for url in urls:
        if isValidBlog(url):
            blogUrl = getBlogFromUrl(url)
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
