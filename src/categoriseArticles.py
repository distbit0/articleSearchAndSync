from inscriptis import get_text as getHtmlText
import shutil

from zeroconf import NonUniqueNameException
import utils
from utils import getConfig
import os
import re
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_completions, completion_is_selected
from prompt_toolkit.styles import Style
from prompt_toolkit.auto_suggest import AutoSuggest, Suggestion
import time
import queue
import concurrent.futures


def getUrlOfArticle(articlePath):
    url = utils.getUrlOfArticle(articlePath)
    if "gist.github.com" in url:
        srcUrl = utils.getSrcUrlOfGitbook(articlePath)
        if srcUrl:
            url = srcUrl
    return url


def getCategories(subCategory="", getSubDirs=True):
    categoryObject = {}
    subDirs = {}
    articleFileFolder = getConfig()["articleFileFolder"]

    def getDirsInDir(folderPath):
        return [f.path for f in os.scandir(folderPath) if f.is_dir()]

    excludedDirs = [
        directory.lower()
        for directory in getConfig()["foldersToExcludeFromCategorisation"]
    ]
    subCategory = subCategory if subCategory else ""
    mainCategories = getDirsInDir(articleFileFolder + subCategory)
    for category in mainCategories:
        fullPath = category
        relativePath = os.path.relpath(fullPath, articleFileFolder)
        folderName = category.split("/")[-1]
        if folderName.lower() in excludedDirs:
            continue
        if getSubDirs:
            subDirs = getCategories(subCategory=relativePath, getSubDirs=False)
        categoryObject[folderName] = {
            "fullPath": fullPath,
            "relativePath": relativePath,
            "subCategories": subDirs,
        }

    return categoryObject


def getTextOfFile(filePath):
    fileText = ""
    fileUrl = ""
    fileExtension = filePath.split(".")[-1].lower()
    if "html" in fileExtension:
        fileHtml = open(filePath, errors="ignore").read()
        fileText = getHtmlText(fileHtml)
        fileUrl = getUrlOfArticle(filePath)
        if "gist.github.com" in fileUrl:
            srcUrl = utils.getSrcUrlOfGitbook(filePath)
            if srcUrl:
                fileUrl = srcUrl
    elif "pdf" in fileExtension:
        fileText = utils.getPdfText(filePath, pages=10)
    elif "epub" in fileExtension:
        fileText = None
    elif "mobi" in fileExtension:
        fileText = None
    if fileText == None:
        fileSnippet = "Article could not be read!"
    else:
        fileSnippet = display_article_snippet(fileText)
    return fileSnippet, fileUrl


def find_first_sentence_position(text):
    # Regular expression pattern for a sentence
    # Exclude sentences containing *, /, or emojis
    pattern = re.compile(
        r"(\b[A-Z](?:(?![*.\/])[^.?!])*[.?!])\s+"  # First sentence pattern
        r"(\b[A-Z](?:(?![*.\/])[^.?!])*[.?!])"  # Second sentence pattern
    )

    match = pattern.search(text)
    return match.start() if match else -1


def display_article_snippet(fileText):
    gistString = "to your computer and use it in GitHub Desktop. Download ZIP"
    if gistString in fileText:
        fileText = fileText.split(gistString)[1]
    indexOfFirstSentence = find_first_sentence_position(fileText)
    snippet = fileText[indexOfFirstSentence:]
    maxLength = getConfig()["wordsUsedToCategorise"]
    words = " ".join(snippet.split()[:maxLength]) + "..."
    return words


class TopCompletionAutoSuggest(AutoSuggest):
    def __init__(self, completer):
        self.completer = completer

    def get_suggestion(self, buffer, document):
        # Get the top completion (if any) from the completer
        completions = list(self.completer.get_completions(document, None))
        bufferLength = len(buffer.text)
        if completions:
            return Suggestion(completions[0].text[bufferLength:])
        return None


def select_category(session, categories, prompt_message):
    category_names = list(categories.keys())
    completer = FuzzyCompleter(WordCompleter(category_names, sentence=True))
    auto_suggest = TopCompletionAutoSuggest(completer)

    # Apply the completer, auto-suggest, and style to the session
    session.completer = completer
    session.auto_suggest = auto_suggest

    # Get user input
    category_input = session.prompt(
        prompt_message,
        complete_while_typing=True,
        pre_run=session.default_buffer.start_completion,
    )

    if category_input.lower() == "read" or category_input in category_names:
        return category_input
    else:
        print("Invalid selection. Please try again.")
        return None


def initPromptSession():
    key_bindings = KeyBindings()
    key_bindings.add("enter", filter=has_completions & ~completion_is_selected)(
        lambda event: (
            event.current_buffer.go_to_completion(0),
            event.current_buffer.validate_and_handle(),
        )
    )
    key_bindings.add("backspace")(
        lambda event: (
            event.current_buffer.delete_before_cursor(1),
            event.current_buffer.start_completion(select_first=False),
        )
    )

    style = Style.from_dict(
        {
            "completion-menu.completion": "bg:#000000 fg:#00ff00",  # black background, green text
            "completion-menu.completion.current": "bg:#000000 fg:#00ff00",  # green background, black text for selected completion
            "scrollbar.background": "#000000",  # black scrollbar background
            "scrollbar.button": "#00ff00",  # green scrollbar button,
            "auto-suggestion": "#0000ff",
        }
    )

    # Create PromptSession with the custom style
    session = PromptSession(
        key_bindings=key_bindings,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=style,
    )
    return session


def fetch_next_file_data(file_path):
    nextFile_text, nextFileUrl = getTextOfFile(file_path)
    return nextFile_text, nextFileUrl, file_path


def getAllFiles():
    # This function recursively finds files in the articleFileFolder and its subfolders.
    article_file_folder = getConfig()["articleFileFolder"]
    doc_formats_to_categorise = getConfig()["docFormatsToMove"]
    all_files = []

    # Recursive function to find files in subdirectories.
    def find_files_in_directory(directory):
        for entry in os.scandir(directory):
            if entry.is_dir():
                # If a directory has subdirectories, process files in this directory.
                if any(os.scandir(entry.path)):
                    find_files_in_directory(entry.path)
            elif (
                entry.is_file()
                and entry.name.split(".")[-1] in doc_formats_to_categorise
            ):
                all_files.append(entry.path)

    find_files_in_directory(article_file_folder)

    all_files = sorted(
        all_files,
        key=lambda path: (path.rsplit("/", 2)[-2], getUrlOfArticle(path)),
    )
    return all_files


def getUncategorisedFileCount(allFiles, categories):
    uncategorized_files = 0
    for file_path in allFiles:
        (
            _,
            isRootDir,
            isInCategoryFolder,
            subcategories,
        ) = isArticleUncategorised(file_path, categories)
        if isRootDir:
            uncategorized_files += 2
        elif isInCategoryFolder and subcategories:
            uncategorized_files += 1
    return uncategorized_files


def isArticleUncategorised(file_path, categories):
    fileFolderName = file_path.split("/")[-2]
    isRootDir = os.path.normpath(file_path.rsplit("/", 1)[0]) == os.path.normpath(
        getConfig()["articleFileFolder"]
    )
    inCategoryFolder = fileFolderName in categories
    subcategories = {}
    if isRootDir:
        subcategories = categories
    elif inCategoryFolder:
        subcategories = categories[fileFolderName].get("subCategories", {})
    isUncategorised = (isRootDir or inCategoryFolder) and subcategories

    return (isUncategorised, isRootDir, inCategoryFolder, subcategories)


def startProcessingNextFile(
    executor, allFiles, next_file_data_queue, file_idx, categories
):
    try:
        nextFilePath = allFiles[file_idx]
    except IndexError:
        return
    isNextFileUncategorised = isArticleUncategorised(nextFilePath, categories)[0]
    if isNextFileUncategorised:
        future = executor.submit(fetch_next_file_data, nextFilePath)
        next_file_data_queue.put((future))


def printArticleDetails(startTime, next_file_data_queue, done, remaining, file_path):
    future = next_file_data_queue.get()
    snippet, fileUrl, filePathFromQueue = future.result()
    fileName = file_path.split("/")[-1]
    avgTimePerArticle = (time.time() - startTime) / done
    snippet = "\n\n" + snippet
    textToPrint = "\n\n\n" + file_path.split("/")[-2] + "\n\n\n" + fileName
    textToPrint += "    (" + str(done) + "/" + str(remaining) + ")"
    textToPrint += (
        "    (avg: "
        + str(round(avgTimePerArticle, 2))
        + "s rem: "
        + str(round(avgTimePerArticle / 3600 * remaining, 1))
        + "h)"
    )
    textToPrint = (
        textToPrint + "\n" + fileUrl + snippet if fileUrl else textToPrint + snippet
    )
    print(textToPrint)


def main():
    allFiles = getAllFiles()
    categories = getCategories()
    next_file_data_queue = queue.Queue()
    session = initPromptSession()
    noUncategorisedFiles = True

    uncategorizedFileCount = getUncategorisedFileCount(
        allFiles, categories
    )  # Replace with your actual function to count uncategorized files

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        startProcessingNextFile(executor, allFiles, next_file_data_queue, 0, categories)

        categorisedFileCount = 0
        startTime = time.time()
        last_subcategory_input = ""
        for file_idx, file_path in enumerate(allFiles):
            startProcessingNextFile(
                executor, allFiles, next_file_data_queue, file_idx + 1, categories
            )
            fileName = file_path.split("/")[-1]
            articleInfo = isArticleUncategorised(
                file_path, categories
            )  # Replace with your actual function
            isUncategorised, subcategories = articleInfo[0], articleInfo[3]
            if isUncategorised:
                noUncategorisedFiles = False
                categorisedFileCount += 1
                printArticleDetails(
                    startTime,
                    next_file_data_queue,
                    categorisedFileCount,
                    uncategorizedFileCount,
                    file_path,
                )
                subcategories["_DELETE"] = subcategories["_NEW"] = subcategories[
                    "_UNDO"
                ] = subcategories["_PARENT"] = subcategories[","] = {}
                subcategory_input = select_category(
                    session, subcategories, "Subcategory: "
                )
                if subcategory_input:
                    if subcategory_input == ",":  ## for repeating last subcategory
                        subcategory_input = last_subcategory_input
                    last_subcategory_input = subcategory_input
                    if subcategory_input == "_DELETE":
                        print("moving to trash: ", file_path)
                        homeDir = os.path.expanduser("~")
                        dest = os.path.join(
                            homeDir, ".local/share/Trash/files/", fileName
                        )
                        shutil.move(file_path, dest)
                        lastMoveDest = dest
                        lastMoveOrigin = file_path
                    elif subcategory_input == "_UNDO":
                        print(f"\nMOVING BACK FROM {lastMoveDest} TO {lastMoveOrigin}")
                        if lastMoveDest:
                            shutil.move(lastMoveDest, lastMoveOrigin)
                    elif subcategory_input == "_PARENT":
                        parentFolderPath = file_path.split("/")[:-2]
                        destPath = "/".join(parentFolderPath) + "/" + fileName
                        print(f"\nMoving {file_path} to {destPath}")
                        shutil.move(file_path, destPath)
                        lastMoveOrigin = file_path
                        lastMoveDest = destPath
                    elif subcategory_input == "_NEW":
                        parentFolderPath = file_path.split("/")[:-1]
                        print(parentFolderPath)
                        newFolderName = input("Enter new folder name: ")
                        newFolderPath = "/".join(parentFolderPath) + "/" + newFolderName
                        os.makedirs(newFolderPath, exist_ok=True)
                        destPath = newFolderPath + "/" + fileName
                        print(f"\nMoving {file_path} to {destPath}")
                        shutil.move(file_path, destPath)
                        lastMoveOrigin = file_path
                        lastMoveDest = destPath
                    else:
                        choice = subcategories.get(subcategory_input)
                        destination = os.path.join(choice["fullPath"], fileName)
                        print(f"\nMoving {file_path} to {destination}")
                        shutil.move(file_path, destination)
                        lastMoveOrigin = file_path
                        lastMoveDest = destination

    return noUncategorisedFiles


if __name__ == "__main__":
    while True:
        noUncategorisedFiles = main()
        if noUncategorisedFiles:
            break
