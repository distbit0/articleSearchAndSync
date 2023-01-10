from utils import getConfig
from eldar import Query
import glob
import utils
import argparse
import subprocess
import os
import shutil
import re


def getPDFPathMappings():
    pdfToTextFileMap = {}
    indexFolderPath = utils.getAbsPath("../storage/indexedPDFs")
    PDFTextFilePaths = glob.glob(indexFolderPath + "/**/*.txt", recursive=True)
    for file in PDFTextFilePaths:
        fileText = open(file).read()
        pdfPath = re.search("PdfFilePath: (.*)\n", fileText).group(1).strip()
        pdfToTextFileMap[file] = pdfPath

    return pdfToTextFileMap


def searchArticlesForQuery(query, subject=""):
    searchFilter = Query(query, ignore_case=True, match_word=False)
    matchingArticleUrls = []
    matchingArticlePaths = []
    articleFilePattern = getConfig()["articleFilePattern"]
    articleFileFolder = getConfig()["articleFileFolder"]
    articlePathPattern = articleFileFolder + articleFilePattern
    allArticlesPaths = glob.glob(articlePathPattern, recursive=True)
    textToPdfFileMap = getPDFPathMappings()
    allArticlesPaths.extend(textToPdfFileMap)
    for articlePath in allArticlesPaths:
        articleSubject = articlePath.split("/")[-2:-1][0]
        if subject.lower() not in articleSubject.lower() and subject:
            continue
        articleText = open(articlePath, errors="ignore").read().strip()
        matchInAricle = searchFilter(articleText)
        if matchInAricle:
            articleUrl = utils.getUrlOfArticle(articlePath)
            if articleUrl not in matchingArticleUrls:
                matchingArticleUrls.append(articleUrl)
                matchingArticlePaths.append(articlePath)

    finalPaths = [
        textToPdfFileMap[path] if path in textToPdfFileMap else path
        for path in matchingArticlePaths
    ]  # include actual pdf paths instead of pdf text file paths

    return matchingArticleUrls, finalPaths


def getCMDArguments():
    parser = argparse.ArgumentParser(description="Boolean search saved articles")
    parser.add_argument("query", help="Query to search for")
    parser.add_argument(
        "subject", nargs="?", help="Subject folders to include in search", default=""
    )
    parser.add_argument(
        "-p", action="store_true", help="Return article paths", dest="returnPaths"
    )
    parser.add_argument(
        "-b", action="store_true", help="Return blog URLs", dest="returnBlogs"
    )
    parser.add_argument(
        "-g",
        action="store_true",
        help="Show article URLs in Gedit",
        dest="openGedit",
    )
    parser.add_argument(
        "-c",
        action="store_true",
        help="Copy article URLs to clipboard",
        dest="copyUrls",
    )
    parser.add_argument(
        "-a",
        action="store_true",
        help="Send URL file to @Voice",
        dest="atVoice",
    )
    parser.add_argument(
        "-s",
        action="store_true",
        help="Sort article URLs alphabetically",
        dest="sort",
    )
    args = parser.parse_args()

    return args


def sendToAtVoice():
    atVoiceUrlOutputFile = (
        getConfig()["atVoiceURLFileFolder"] + getConfig()["atVoiceURLTmpFile"]
    )
    shutil.copyfile(
        utils.getAbsPath("../output/searchResultUrls.txt"), atVoiceUrlOutputFile
    )
    print("\n\nSent article URLs to @Voice (" + atVoiceUrlOutputFile + ")")


if __name__ == "__main__":
    args = getCMDArguments()
    articleUrls, articlePaths = searchArticlesForQuery(args.query, args.subject)

    if args.sort:
        articleUrls = sorted(articleUrls)

    utils.addUrlToUrlFile(
        articleUrls, utils.getAbsPath("../output/searchResultUrls.txt"), True
    )

    print("Article URLs:\n\n" + "\n".join(articleUrls))

    if args.returnPaths:
        print("\n\nArticle paths:\n\n" + "\n".join(articlePaths))

    if args.returnBlogs:
        blogUrls = utils.getBlogsFromUrls(articleUrls)
        print("\n\nBlog URLs:\n\n" + "\n".join(blogUrls))

    if args.openGedit:
        subprocess.Popen(["gedit", utils.getAbsPath("../output/searchResultUrls.txt")])

    if args.copyUrls:
        os.system(
            "xclip -sel c < " + utils.getAbsPath("../output/searchResultUrls.txt")
        )
        print("\n\nCopied article URLs to clipboard")

    if args.atVoice:
        sendToAtVoice()
