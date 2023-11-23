from inscriptis import get_text as getHtmlText
import shutil
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
import threading
import queue


def find_first_sentence_position(text):
    # Regular expression pattern for a sentence
    # Exclude sentences containing *, /, or emojis
    pattern = re.compile(
        r"(\b[A-Z](?:(?![*.\/])[^.?!])*[.?!])\s+"  # First sentence pattern
        r"(\b[A-Z](?:(?![*.\/])[^.?!])*[.?!])"  # Second sentence pattern
    )

    match = pattern.search(text)
    return match.start() if match else -1


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
        fileHtml = open(filePath).read()
        fileText = getHtmlText(fileHtml)
        fileUrl = utils.getUrlOfArticle(filePath)
    if "pdf" in fileExtension:
        fileText = utils.getPdfText(filePath)

    fileSnippet = display_article_snippet(fileText)
    return fileSnippet, fileUrl


def display_article_snippet(fileText):
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
            "suggestion": "#0000ff",
        }
    )

    # Create PromptSession with the custom style
    session = PromptSession(
        key_bindings=key_bindings,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=style,
    )
    return session


def fetch_next_file_data(file_path, output_queue):
    nextFile_text, nextFileUrl = getTextOfFile(file_path)
    output_queue.put((nextFile_text, nextFileUrl))


def getAllFiles():
    # This function recursively finds files in the articleFileFolder and its subfolders.
    article_file_folder = getConfig()["articleFileFolder"]
    doc_formats_to_categorise = getConfig()["docFormatsToAutoCategorise"]
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

    all_files = sorted(all_files)
    return all_files


def printArticleDetails(snippet, fileName, done, remaining, filePath, fileUrl):
    snippet = "\n\n" + snippet
    textToPrint = "\n\n\n\n\n\n" + fileName
    textToPrint += "    (" + str(done) + "/" + str(remaining) + ")"
    textToPrint += "\n" + filePath
    textToPrint = (
        textToPrint + "\n" + fileUrl + snippet if fileUrl else textToPrint + snippet
    )
    print(textToPrint)


def getUncategorisedFileCount(files_in_root_dir, categories):
    uncategorized_files = 0
    for file_path in files_in_root_dir:
        fileFolderName = file_path.split("/")[-2]
        isRootDir = os.path.normpath(file_path.rsplit("/", 1)[0]) == os.path.normpath(
            getConfig()["articleFileFolder"]
        )
        if fileFolderName in categories or isRootDir:
            uncategorized_files += 1
    return uncategorized_files


def main():
    files_in_root_dir = getAllFiles()
    categories = getCategories()
    session = initPromptSession()
    next_file_data_queue = queue.Queue()

    uncategorized_files = getUncategorisedFileCount(files_in_root_dir, categories)

    if files_in_root_dir:
        threading.Thread(
            target=fetch_next_file_data,
            args=(files_in_root_dir[0], next_file_data_queue),
        ).start()

    categorisedFiles = 0
    for file_idx, file_path in enumerate(files_in_root_dir):
        (
            articleSnippet,
            fileUrl,
        ) = next_file_data_queue.get()

        fileName = file_path.split("/")[-1]
        filePath = "/".join(file_path.split("/")[:-1])
        threading.Thread(
            target=fetch_next_file_data,
            args=(files_in_root_dir[file_idx + 1], next_file_data_queue),
        ).start()

        isRootDir = os.path.normpath(filePath) == os.path.normpath(
            getConfig()["articleFileFolder"]
        )
        fileFolderName = filePath.split("/")[-1]
        if fileFolderName in categories or isRootDir:
            categorisedFiles += 1

            printArticleDetails(
                articleSnippet,
                fileName,
                categorisedFiles,
                uncategorized_files,
                filePath,
                fileUrl,
            )
            subcategories = (
                categories
                if isRootDir
                else categories[fileFolderName].get("subCategories", {})
            )
            subcategories["_DELETE"] = {}
            if subcategories:
                subcategory_input = select_category(
                    session, subcategories, "Subcategory: "
                )
                if subcategory_input:
                    if subcategory_input == "_DELETE":
                        print(f"\nDeleting {file_path}")
                        os.remove(file_path)
                    else:
                        choice = subcategories.get(subcategory_input)
                        destination = os.path.join(choice["fullPath"], fileName)
                        print(f"\nMoving {file_path} to {destination}")
                        shutil.move(file_path, destination)


if __name__ == "__main__":
    main()
