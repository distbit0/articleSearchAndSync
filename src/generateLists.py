from .utils import getConfig
from . import utils, db
import os


def updateLists():
    listToTagMappings = getConfig()["listToTagMappings"]

    for listName, listInfo in listToTagMappings.items():
        all_tags, any_tags, not_any_tags, readState, disabled, formats = (
            listInfo.get("all_tags", []),
            listInfo.get("any_tags", []),
            listInfo.get("not_any_tags", []),
            listInfo.get("readState", "unread"),
            listInfo.get("disabled", False),
            listInfo.get("formats", getConfig()["docFormatsToMove"]),
        )
        if disabled:
            utils.deleteListIfExists(listName)
            continue

        print(listName, listInfo)
        articlePathsForList = db.searchArticlesByTags(
            all_tags=all_tags,
            any_tags=any_tags,
            not_any_tags=not_any_tags,
            readState=readState,
            formats=formats,
        )

        articlePathsForList = [
            x[0] for x in sorted(articlePathsForList.items(), key=lambda x: x[1])
        ]
        # print(articlePathsForList)
        utils.addArticlesToList(listName, articlePathsForList)


if __name__ == "__main__":
    updateLists()
