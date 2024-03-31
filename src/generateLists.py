from numpy import sort
from utils import getConfig
import utils
import os


def updateLists():
    listFolderMappings = getConfig()["listToFolderMappings"]

    for listName, listInfo in listFolderMappings.items():
        listFolders, readState, query, disabled = (
            listInfo.get("folders", []),
            listInfo.get("readState", "unread"),
            listInfo.get("query", "*"),
            listInfo.get("disabled", False),
        )
        if disabled:
            utils.deleteListIfExists(listName)
            continue

        print(listName, listInfo)
        articlePathsForList = utils.searchArticlesForQuery(
            query,
            subjects=listFolders,
            readState=readState,
            formats=getConfig()["docFormatsToMove"],
        )

        articlePathsForList = [
            x[0] for x in sorted(articlePathsForList.items(), key=lambda x: x[1])
        ]

        utils.addArticlesToList(listName, articlePathsForList)


if __name__ == "__main__":
    updateLists()
