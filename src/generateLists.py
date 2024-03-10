from utils import getConfig
import utils
import os


def updateLists():
    listFolderMappings = getConfig()["listToFolderMappings"]

    for listName, listInfo in listFolderMappings.items():
        listFolders, onlyUnread, query = (
            listInfo.get("folders", []),
            listInfo.get("onlyUnread", True),
            listInfo.get("query", "*"),
        )
        print(listName, listInfo)
        articlePathsForList = utils.searchArticlesForQuery(
            query,
            subjects=listFolders,
            onlyUnread=onlyUnread,
            formats=getConfig()["docFormatsToMove"],
        )
        pathsSortedByUrl = [
            x[0] for x in sorted(articlePathsForList.items(), key=lambda x: x[1])
        ]

        utils.addArticlesToList(listName, pathsSortedByUrl)


if __name__ == "__main__":
    updateLists()
