from inscriptis import get_text as getHtmlText
import shutil
import utils
from utils import getConfig
import os
import glob
import re
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter
from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_completions, completion_is_selected
from prompt_toolkit.styles import Style


def find_first_sentence_position(text):
    # Regular expression pattern for a sentence
    # Exclude sentences containing *, /, or emojis
    pattern = re.compile(
        r"(\b[A-Z](?:(?![*.\/])[^.?!])*[.?!])\s+"  # First sentence pattern
        r"(\b[A-Z](?:(?![*.\/])[^.?!])*[.?!])"  # Second sentence pattern
    )

    match = pattern.search(text)
    return match.start() if match else -1


def getUncategorisedFiles():
    filesInRootDir = []
    articleFileFolder = getConfig()["articleFileFolder"]
    docFormatsToCategorise = getConfig()["docFormatsToAutoCategorise"]
    for format in docFormatsToCategorise:
        articleFilePattern = "*." + format
        articlePathPattern = articleFileFolder + articleFilePattern
        filesInRootDir.extend(list(glob.glob(articlePathPattern)))

    return filesInRootDir


def getCategories(subCategory="", getSubDirs=True):
    categoryObject = {}
    subDirs = {}
    categoryDescriptions = getConfig()["categoryDescriptions"]
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
        description = (
            categoryDescriptions[relativePath]
            if relativePath in categoryDescriptions
            else ""
        )
        if getSubDirs:
            subDirs = getCategories(subCategory=relativePath, getSubDirs=False)
        categoryObject[folderName] = {
            "fullPath": fullPath,
            "relativePath": relativePath,
            "description": description,
            "subCategories": subDirs,
        }

    return categoryObject


def getTextOfFile(filePath):
    fileText = ""
    fileExtension = filePath.split(".")[-1].lower()
    if "html" in fileExtension:
        fileHtml = open(filePath).read()
        fileText = getHtmlText(fileHtml)
    if "pdf" in fileExtension:
        fileText = utils.getPdfText(filePath)

    return fileText


def display_article_snippet(fileText):
    indexOfFirstSentence = find_first_sentence_position(fileText)
    snippet = fileText[indexOfFirstSentence:]
    maxLength = getConfig()["wordsUsedToCategorise"]
    words = " ".join(snippet.split()[:maxLength]) + "..."
    print(words)


def select_category(session, categories, prompt_message):
    """
    Function to select a category or subcategory using fuzzy search.

    :param session: PromptSession object for interactive prompt.
    :param categories: Dictionary of categories or subcategories.
    :param prompt_message: String, message to display on the prompt.
    :return: Selected category name or 'read'.
    """
    category_names = list(categories.keys())
    session.completer = FuzzyCompleter(WordCompleter(category_names, sentence=True))

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


def main():
    filesInRootDir = getUncategorisedFiles()
    categories = getCategories()

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

    for filePath in filesInRootDir:
        fileText = getTextOfFile(filePath)

        print(f"\n\n\n\n{filePath.split('/')[-1]}\n")
        display_article_snippet(fileText)
        category_input = select_category(
            session,
            categories,
            "Category: ",
        )

        selected_category = categories.get(category_input)
        if not selected_category:
            continue

        subcategories = selected_category.get("subCategories", {})
        subcategory_input = ""
        if subcategories:
            subcategory_input = select_category(session, subcategories, "Subcategory: ")

        if subcategory_input:
            choice = subcategories.get(subcategory_input)
        elif len(subcategories) == 0 and selected_category:
            choice = selected_category
        else:
            continue
        source = filePath
        destination = os.path.join(choice["fullPath"], filePath.split("/")[-1])
        print(f"Moving {source} to {destination}")
        shutil.move(source, destination)


if __name__ == "__main__":
    main()
