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

    return fileText, fileUrl


def display_article_snippet(fileText):
    indexOfFirstSentence = find_first_sentence_position(fileText)
    snippet = fileText[indexOfFirstSentence:]
    maxLength = getConfig()["wordsUsedToCategorise"]
    words = " ".join(snippet.split()[:maxLength]) + "..."
    print(words)


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


# This function now recursively finds files in the articleFileFolder and its subfolders.
def get_uncategorised_files():
    article_file_folder = getConfig()["articleFileFolder"]
    doc_formats_to_categorise = getConfig()["docFormatsToAutoCategorise"]
    uncategorised_files = []

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
                uncategorised_files.append(entry.path)

    find_files_in_directory(article_file_folder)

    uncategorised_files = sorted(uncategorised_files)
    return uncategorised_files


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
            "scrollbar.button": "#00ff00",  # green scrollbar button
        }
    )

    # Create PromptSession with the custom style
    session = PromptSession(
        key_bindings=key_bindings,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=style,
    )
    return session


# Main function to process each file.
def main():
    files_in_root_dir = get_uncategorised_files()
    categories = getCategories()
    session = initPromptSession()

    for file_path in files_in_root_dir:
        file_text, fileUrl = getTextOfFile(file_path)
        print(f"\n\n\n\n\n\n{file_path.split('/')[-1]}")
        if fileUrl:
            print(fileUrl, "\n")
        display_article_snippet(file_text)
        path_segments = file_path.split(os.sep)
        for i in range(len(path_segments) - 1, 0, -1):
            pathUpToCurrent = "/".join(path_segments[:i])
            isRootDir = os.path.normpath(pathUpToCurrent) == os.path.normpath(
                getConfig()["articleFileFolder"]
            )

            if path_segments[i] in categories or isRootDir:
                subcategories = (
                    categories
                    if isRootDir
                    else categories[path_segments[i]].get("subCategories", {})
                )
                subcategories["DELETE"] = {}
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
                            destination = os.path.join(
                                choice["fullPath"], path_segments[-1]
                            )
                            print(f"\nMoving {file_path} to {destination}")
                            shutil.move(file_path, destination)

                            break
                break


if __name__ == "__main__":
    main()
