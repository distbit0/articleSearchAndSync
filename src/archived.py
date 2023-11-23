from inscriptis import get_text as getHtmlText
import utils
from utils import getConfig, getPdfText
import os
import glob
import openai
import re
import tiktoken
import time

openai.api_key = getConfig()["openaiApiKey"]


topCategoriesInstructions = """
________INSTRUCTIONS________

Below is an article and a list of categories and their sub-categories.
Chose the top two categories which are most relevant and most specific to the article.
Do not include any sub-categories. Only a comma-separated list of the two most relevant categories.
the sub categories are only provided to allow you to better understand each category.
Do not create new categories. Only chose categories from the provided list.
ONLY RESPOND WITH THE comma separated list of categories. NOTHING ELSE.
E.g. "category1, category2"
"""

finalCategoryInstructions = """
________INSTRUCTIONS________

Below is an article and a list of categories.
Chose the category and sub category which are most relevant and most specific to the article.
Only select one category/sub category pair.
Use the sub categories under each category to better understand each category.
Do not create new categories or sub categories. Only chose categories/sub categories from the provided list.
ONLY RESPOND WITH THE NAME OF THE category and sub category. NOTHING ELSE. Seperate them via a "/".
E.g. "category/sub category"
If no sub category exists under the most relevant category, just return the category without a "/" or a sub category.
"""


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
    subCategory = "/" + subCategory if subCategory else ""
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
        fileText = getPdfText(filePath)

    return fileText


def validateCategories(categories, top_categories):
    categoriesAreValid = True
    errorMessage = ""
    outputCategories = []
    for category in top_categories:
        found = False
        for cat in categories:
            if category.lower() == cat.lower():
                found = True
                outputCategories.append(cat)
                break
        if not found:
            errorMessage += (
                "Category provided ("
                + category
                + ") not found. Chose another category from the list. "
            )

    if errorMessage != "":
        categoriesAreValid = False
        outputCategories = []
    return categoriesAreValid, outputCategories, errorMessage


def checkIfCategoryExists(categories, category, subcategory):
    # Convert the input category and subcategory to lowercase for case-insensitive comparison
    category_lower = category.lower()
    subcategory_lower = subcategory.lower()
    errorMessage = ""

    for cat, details in categories.items():
        # Check if the main category matches, case-insensitive
        if cat.lower() == category_lower:
            # Check if there are subcategories
            if "subCategories" in details and len(details["subCategories"]) > 0:
                for subcat in details["subCategories"]:
                    # Check if the subcategory matches, case-insensitive
                    if subcat.lower() == subcategory_lower:
                        return True, [cat, subcat], errorMessage
                errorMessage = (
                    "Subcategory provided ("
                    + subcategory
                    + ") not found. Chose another subcategory from the list."
                )
                return False, [None, None], errorMessage
            else:
                # If no subcategories, return the main category
                return True, [cat, ""], errorMessage
    errorMessage = (
        "Category provided ("
        + category  # Convert the input category and subcategory to lowercase for case-insensitive comparison
        + ") not found. Chose another category/subcategory pair from the list."
    )
    return False, [None, None], errorMessage


def askGptForTopCategories(categories, combinedArticleText):
    categoriesText = []
    for category in categories:
        description = categories[category]["description"]
        categoryText = '"' + category + '"'
        if description != "":
            categoryText += " description: " + description
        subCategories = categories[category]["subCategories"]
        subCategoriesText = '\n   Subcategories: "' + '", "'.join(subCategories) + '"'
        categoryText += subCategoriesText
        categoriesText.append(categoryText)

    categoryText = "\n\n".join(categoriesText)

    prompt = (
        topCategoriesInstructions
        + "\n\n________ARTICLE________\n\n"
        + combinedArticleText
        + "\n\n________CATEGORIES________\n\n"
        + categoryText
    )
    attempts = 0
    max_attempts = 5
    top_categories = []
    conversation = [{"role": "user", "content": prompt}]
    print(
        "prompt tokens",
        len(tiktoken.encoding_for_model(modelName).encode(prompt)),
    )
    while not top_categories and attempts < max_attempts:
        try:
            response = (
                openai.ChatCompletion.create(
                    model=modelName,
                    messages=conversation,
                )[
                    "choices"
                ][0]["message"]["content"]
                .strip()
                .replace('"', "")
            )
            conversation.append({"role": "assistant", "content": response})
            top_categories = [cat.strip() for cat in response.split(",")]
            if len(top_categories) != 2:
                top_categories = []
                errorMessage = (
                    "Please provide exactly 2 categories, separated by commas."
                )
                conversation.append({"role": "user", "content": errorMessage})
            else:
                (
                    categoriesAreValid,
                    top_categories,
                    errorMessage,
                ) = validateCategories(categories, top_categories)
                if not categoriesAreValid:
                    conversation.append({"role": "user", "content": errorMessage})
            if errorMessage:
                print(errorMessage)

        except Exception as e:
            print(f"An error occurred: {e}")
            if "rate-limits" in str(e):
                errorMessage = "OpenAI API rate limit exceeded. Please try again later."
                time.sleep(12)
                attempts -= 1
            else:
                break
        attempts += 1

    return top_categories


def askGptToClassify(categories, combinedArticleText):
    categoriesText = []
    for category in categories:
        description = categories[category]["description"]
        categoryText = '"' + category + '"'
        if description != "":
            categoryText += " description: " + description
        subCategories = categories[category]["subCategories"]
        subCategoriesText = '\n   Subcategories: "' + '", "'.join(subCategories) + '"'
        categoryText += subCategoriesText
        categoriesText.append(categoryText)

    categoryText = "\n\n".join(categoriesText)

    prompt = (
        finalCategoryInstructions
        + "\n\n________ARTICLE________\n\n"
        + combinedArticleText
        + "\n\n________CATEGORIES________\n\n"
        + categoryText
    )
    category = subcategory = ""
    attempts = 0
    max_attempts = 5  # Set a reasonable number of attempts
    validOutput = False
    errorMessage = ""
    conversation = [{"role": "user", "content": prompt}]
    while not validOutput and attempts < max_attempts:
        try:
            chosenCategory = (
                openai.ChatCompletion.create(
                    model=modelName,
                    messages=conversation,
                )[
                    "choices"
                ][0]["message"]["content"]
                .strip()
                .replace('"', "")
            )
            conversation.append({"role": "assistant", "content": chosenCategory})
            print(f"Chosen category: {chosenCategory}")
            if "/" in chosenCategory:
                category, subcategory = chosenCategory.split("/")
            else:
                category = chosenCategory
                subcategory = ""
            validOutput, [category, subcategory], errorMessage = checkIfCategoryExists(
                categories, category, subcategory
            )
            if not validOutput:
                print(errorMessage)
                conversation.append(
                    {
                        "role": "user",
                        "content": errorMessage
                        + " DO NOT RESPOND WITH ANYTHING EXCEPT THE CATEGORY and SUBCATEGORY (if any).",
                    }
                )
            print(f"Valid output: {validOutput}", category, "||", subcategory)
            print(
                "prompt tokens",
                len(tiktoken.encoding_for_model(modelName).encode(prompt)),
            )
        except Exception as e:
            print(f"An error occurred: {e}")
            if "rate-limits" in str(e):
                errorMessage = "OpenAI API rate limit exceeded. Please try again later."
                time.sleep(12)
                attempts -= 1
            else:
                break
        attempts += 1

    return [category, subcategory] if validOutput else [None, None]


def categoriseArticles(filePath, fileText):
    lengthOfCategorisationSnippet = getConfig()["wordsUsedToCategorise"]
    indexOfFirstSentence = find_first_sentence_position(fileText)
    textFromSentence = fileText[indexOfFirstSentence:]
    words = textFromSentence.split()
    combinedArticleText = (
        "Article title:"
        + filePath.split("/")[-1]
        + "\nArticle url:"
        + utils.getUrlOfArticle(filePath)
        + "\nArticle contents:\n"
        + " ".join(words[:lengthOfCategorisationSnippet])
    )
    print("\n\n\n\n\n\n" + combinedArticleText)
    categoriesAndSubCategories = getCategories()
    top_categories = askGptForTopCategories(
        categoriesAndSubCategories, combinedArticleText
    )
    print("\n\n\nTOP CATEGORIES", top_categories)
    categoriesAndSubCategories = {
        category: categoriesAndSubCategories[category]
        for category in categoriesAndSubCategories
        if category in top_categories
    }
    if len(categoriesAndSubCategories) == 0:
        print("Could not get top categories for article.")
        return
    category, subcategory = askGptToClassify(
        categoriesAndSubCategories, combinedArticleText
    )


if __name__ == "__main__":
    modelName = "gpt-4-1106-preview"
    filesInRootDir = getUncategorisedFiles()
    for filePath in filesInRootDir[0:10]:
        fileText = getTextOfFile(filePath)
        categoriseArticles(filePath, fileText)


"categoryDescriptions": {
        "Machine and human thought": "relates to epistemology, machine learning, agi, consciousness, memory, tools for thought and zettelkasten",
        "Decentralised Finance": "Relates to on-chain/smart-contract based decentralised finance protocols and projects.",
        "Cryptocurrency": "ONLY relates to cryptocurrencies/blockchains. Does not include defi/decentralised finance protocols.",
        "Reputation arbitration and identity": "Does not include defi/decentralised finance protocols.",
        "Futurism": "Relates to future/advanced technology speculation and sci fi.",
        "Geopol and war": "",
        "Business and entrepreneurship": "",
        "Mathematics": "Does not include cryptography or machine learning/AI maths.",
        "Law": "",
        "Finance": "Does not include decentralised finance. Only content relating to finance itself.",
        "Physics": "",
        "Economics": "Relates to Economic theory. Not politics content.Does not include finance/or decentralised finance.",
        "Political Philosophy": "Politics related. Does not include economic theory. Includes normative/ideological content. Does not include anarcho capitalist material.",
        "Climate Change": "Relating to science and economics of climate change",
        "Augmented reality": "Any content relating to augmented reality/AR/XR/VR",
        "Cryptography & number theory": "Any maths or other content re: cryptography. Except for ZK which goes in decentralised finance.",
        "Computer Science": "Does not include machine learning, smart contracts, blockchain, cryptography, decenralised finance.",
        "distributed protocols": "Any decentralised protocols. Does not include decentralised finance protocols.",
        "Biology": "",
        "Survival": "Survival related material",
        "Anarcho capitalism": "Anarcho capitalist material.",
        "Philosophy (excl. epistemology)": "Any philosophy material except for that related to epistemology or otherwise in machine and human thought"
    }