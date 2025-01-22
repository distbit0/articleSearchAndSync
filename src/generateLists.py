from numpy import sort
from utils import getConfig
import utils
import os


def updateLists():
    listFolderMappings = getConfig()["listToFolderMappings"]

    for listName, listInfo in listFolderMappings.items():
        listFolders, readState, query, disabled, formats = (
            listInfo.get("folders", []),
            listInfo.get("readState", "unread"),
            listInfo.get("query", "*"),
            listInfo.get("disabled", False),
            listInfo.get("formats", getConfig()["docFormatsToMove"]),
        )
        if disabled:
            utils.deleteListIfExists(listName)
            continue

        print(listName, listInfo)
        articlePathsForList = utils.searchArticlesForQuery(
            query,
            subjects=listFolders,
            readState=readState,
            formats=formats,
        )

        articlePathsForList = [
            x[0] for x in sorted(articlePathsForList.items(), key=lambda x: x[1])
        ]

        utils.addArticlesToList(listName, articlePathsForList)


if __name__ == "__main__":
    updateLists()
