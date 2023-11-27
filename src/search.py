from utils import getConfig
import utils
import argparse
import subprocess
import shutil
import os

# import semanticSearch


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
        help="Sort article urls alphabetically",
        dest="sort",
    )
    args = parser.parse_args()

    return args


def sendToAtVoice():
    atVoiceUrlOutputFile = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", "Temp.txt"
    )
    shutil.copyfile(
        utils.getAbsPath("../output/searchResultUrls.txt"), atVoiceUrlOutputFile
    )
    print("\n\nSent article URLs to @Voice (" + atVoiceUrlOutputFile + ")")


def main():
    args = getCMDArguments()
    ###################################
    # profiler = cProfile.Profile()
    # profiler.enable()
    subjectList = [args.subject] if args.subject else []
    articles = utils.searchArticlesForQuery(
        args.query, subjectList, onlyUnread=False, formats=["html", "pdf"]
    )
    # profiler.disable()
    # stats = pstats.Stats(profiler).sort_stats("cumtime")
    # stats.print_stats()
    articleUrls = [url for url in articles.values() if url]
    articlePaths = list(articles.keys())
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


if __name__ == "__main__":
    main()
