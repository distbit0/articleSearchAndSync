import re
import glob
import urlexpander
from os import path
import json
from pathlib import Path


def formatUrl(url):
    if "t.co/" in url:
        url = urlexpander.expand(url)
    if ".medium.com" not in url:
        url = url.replace("medium.com", "scribe.rip").strip()
    url = re.sub(r"\?gi=.*", r"", url)
    url = re.sub(r"\&gi=.*", r"", url)
    return url


def getUrlOfArticle(articleFilePath):
    extractedUrl = ""
    with open(articleFilePath) as _file:
        fileText = _file.read()
        urlPatterns = getConfig()["urlPatterns"]
        for urlPattern in urlPatterns:
            match = re.search(urlPattern, fileText)
            if match:
                extractedUrl = formatUrl(match.group(1).strip())
                break

    return extractedUrl


def getUrlsInLists(subject=""):
    extractedUrls = []
    articleFilePattern = getConfig()["articleFilePattern"]
    articleFileFolder = getConfig()["articleFileFolder"]
    articlePathPattern = articleFileFolder + articleFilePattern
    for f in glob.glob(articlePathPattern, recursive=True):
        articleSubject = f.split("/")[-2:-1][0]
        if subject.lower() not in articleSubject.lower() and subject:
            continue
        extractedUrls.append(getUrlOfArticle(f))
    return extractedUrls


def getUrlsFromFile(urlFile):
    allUrls = []
    with open(urlFile, "r") as allUrlsFile:
        fileText = allUrlsFile.read()
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
    if "gist.github.com" in url:
        blog = re.search(r"(https:\/\/gist.github.com\/.*)\/", url).group(1).strip()
    elif "https://scribe.rip" in url:
        blog = re.search(r"(https:\/\/scribe.rip\/.*)\/", url).group(1).strip()
    elif "https://mirror.xyz" in url:
        blog = re.search(r"(https:\/\/mirror.xyz\/.*?)\/", url + "/").group(1).strip()
    else:
        blog = re.search(r"^(?:http[s]*://[^/]+)", url).group(0).strip()

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
    indexedPDFFolders = getConfig()["indexedPDFFolders"]
    pdfExcludedBlogs = []
    for folder in indexedPDFFolders.values():
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
