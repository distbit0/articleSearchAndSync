from utils import getConfig, getArticlesFromList
import utils
import os


def checkListExists(listName):
    listPath = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", listName + ".rlst"
    )
    return os.path.exists(listPath)


def addArticlesToList(listName, articlePathsForList):
    if not checkListExists(listName):
        print("List " + listName + " does not exist")
        return
    listPath = os.path.join(
        getConfig()["atVoiceFolderPath"], ".config", listName + ".rlst"
    )
    articleNamesInList = getArticlesFromList(listName)
    # print("\n\n\n\n\n\n\n\n" + listName, "\n", articleNamesInList)
    droidEbooksFolderPath = getConfig()["droidEbooksFolderPath"]
    articleFileFolder = getConfig()["articleFileFolder"]
    linesToAppend = []
    for articlePath in articlePathsForList:
        articleName = articlePath.split("/")[-1]
        relativeArticlePath = os.path.relpath(articlePath, articleFileFolder)
        droidArticlePath = os.path.join(droidEbooksFolderPath, relativeArticlePath)
        if articleName not in articleNamesInList:
            displayName = articleName.split(".")[0]
            linesToAppend.append(droidArticlePath + "\t" + displayName)
    newListText = "\n".join(linesToAppend)
    currentListText = open(listPath).read().strip()
    combinedListText = currentListText + "\n" + newListText
    print(
        "\n\n\n\n\n\n\n\nAdding the following articles to list: " + listName,
        "\n",
        newListText,
    )
    with open(listPath, "w") as f:
        f.write(combinedListText)


def updateLists():
    listFolderMappings = getConfig()["listToFolderMappings"]

    for listName, listInfo in listFolderMappings.items():
        listFolders, onlyUnread = listInfo["folders"], listInfo["onlyUnread"]
        articlePathsForList = utils.searchArticlesForQuery(
            "*", listFolders, onlyUnread
        )[1]
        addArticlesToList(listName, articlePathsForList)


if __name__ == "__main__":
    updateLists()
