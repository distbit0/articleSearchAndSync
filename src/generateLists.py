from .utils import getConfig
from . import utils, db
import os


def create_prefixed_html(original_path, prefixed_path, summary):
    """
    Create a copy of an HTML/MHTML file with summary prefixed as a <p> element.

    Args:
        original_path: Path to the original HTML/MHTML file
        prefixed_path: Path where the prefixed copy will be saved
        summary: Summary text to prefix to the file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Read the original file
        with open(original_path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read()

        # Add the summary as a <p> element at the beginning of the content
        summary_html = f"<p>{summary}</p>"

        # Handle different document structures for HTML files
        if "<body" in content:
            # Insert after the body tag
            body_start = content.find("<body")
            # Find the end of the body tag
            body_tag_end = content.find(">", body_start) + 1
            modified_content = (
                content[:body_tag_end] + summary_html + content[body_tag_end:]
            )
        else:
            # No body tag, try to insert after <html> or just prepend
            if "<html" in content:
                html_start = content.find("<html")
                html_tag_end = content.find(">", html_start) + 1
                modified_content = (
                    content[:html_tag_end] + summary_html + content[html_tag_end:]
                )

        # Write the modified content to the new file
        with open(prefixed_path, "w", encoding="utf-8") as file:
            file.write(modified_content)

        return True
    except Exception as e:
        print(f"Error prefixing article {os.path.basename(original_path)}: {str(e)}")
        return False


def process_article_for_prefixing(path, prefixed_folder):
    """
    Process an article file for prefixing with summary.

    Args:
        path: Path to the article file
        prefixed_folder: Path to the prefixed folder

    Returns:
        str: Path to use (either original or prefixed)
    """
    file_ext = os.path.splitext(path)[1].lower()

    # Only process html and mhtml files
    if file_ext not in [".html", ".mhtml"]:
        return path

    # Get the filename
    filename = os.path.basename(path)

    # Get article summary from database
    article_data = db.get_article_by_file_name(filename)

    if not (article_data and article_data.get("summary")):
        return path

    # Create the path for the prefixed copy
    prefixed_path = os.path.join(prefixed_folder, filename)

    # Only copy and modify if the file hasn't been prefixed yet
    if not os.path.exists(prefixed_path):
        success = create_prefixed_html(path, prefixed_path, article_data["summary"])
        if success:
            return prefixed_path
        return path
    else:
        # If prefixed file already exists, use that path
        return prefixed_path


def updateLists():
    listToTagMappings = getConfig()["listToTagMappings"]

    for listName, listInfo in listToTagMappings.items():
        (
            all_tags,
            any_tags,
            not_any_tags,
            readState,
            disabled,
            formats,
            prefixSummary,
        ) = (
            listInfo.get("all_tags", []),
            listInfo.get("any_tags", []),
            listInfo.get("not_any_tags", []),
            listInfo.get("readState", "unread"),
            listInfo.get("disabled", False),
            listInfo.get("formats", getConfig()["docFormatsToMove"]),
            listInfo.get("prefixSummary", False),
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

        # Add articles to the list without prefixing
        utils.addArticlesToList(listName, articlePathsForList)

        # Process prefixing if required
        if prefixSummary:
            prefixed_folder = os.path.join(
                getConfig()["articleFileFolder"], "prefixedArticles"
            )
            # Create prefixedArticles directory if it doesn't exist
            os.makedirs(prefixed_folder, exist_ok=True)

            # Get all articles currently in the list
            list_articles = utils.getArticlesFromList(listName)

            # Apply prefixing to all articles in the list
            updated_article_paths = []
            for filename in list_articles:
                path = os.path.join(getConfig()["articleFileFolder"], filename)
                # Only process if the path exists
                if os.path.exists(path):
                    updated_path = process_article_for_prefixing(path, prefixed_folder)
                    updated_article_paths.append(updated_path)
                else:
                    # Keep original path if file doesn't exist
                    updated_article_paths.append(path)

            # Update the list with the prefixed paths, overwriting existing entries
            # but preserving the headers
            if updated_article_paths:
                utils.addArticlesToList(listName, updated_article_paths, overwrite=True)


if __name__ == "__main__":
    updateLists()
