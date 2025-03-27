import pysnooper
import re
from .utils import getConfig
import sys
from . import utils, db
from bs4 import BeautifulSoup
import os
import requests
import time
import json
import zipfile
import tempfile
import markdown
from dotenv import load_dotenv
import concurrent.futures
import subprocess

from loguru import logger

# Configure loguru logger
# logger.remove()

# Load environment variables from .env file
load_dotenv()

# Get the API token from the environment variable MINERU_API
API_TOKEN = os.getenv("MINERU_API")
if not API_TOKEN:
    raise ValueError("MINERU_API token not found in .env")

# Global headers for Mineru API requests
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {API_TOKEN}"}

# -------------------------------------------------------------------
# PDF-to-EPUB Conversion Functions (using the Mineru API)
# -------------------------------------------------------------------


def get_upload_url(file_path):
    """
    Request an upload URL from Mineru for the given file.
    """
    filename = os.path.basename(file_path)
    payload = {
        "enable_formula": True,
        "language": "en",
        "layout_model": "doclayout_yolo",
        "enable_table": True,
        "files": [{"name": filename, "is_ocr": False, "data_id": filename}],
    }
    url = "https://mineru.net/api/v4/file-urls/batch"
    response = requests.post(url, headers=HEADERS, json=payload, timeout=10)
    if response.status_code != 200:
        raise Exception(
            f"Failed to get upload URL. Status code: {response.status_code}\nResponse: {response.text}"
        )

    result = response.json()
    if result.get("code") not in [0, 200]:
        raise Exception(f"Error from upload URL API: {result}")

    data = result.get("data", {})
    if "file_urls" not in data or "batch_id" not in data:
        raise Exception("Invalid response from upload URL API")
    return data["batch_id"], data["file_urls"]


def upload_file(upload_url, file_path):
    """
    Upload the file to the provided URL.
    """
    logger.debug(f"Uploading file ({file_path}) to: {upload_url}")
    with open(file_path, "rb") as f:
        response = requests.put(upload_url, data=f, timeout=60)
    if response.status_code != 200:
        raise Exception(f"Failed to upload file. Status code: {response.status_code}")
    return True


def poll_batch_task_result(batch_id, max_retries=8, retry_interval=10):
    """
    Poll the Mineru batch results endpoint until the parsing task is done.
    """
    result_url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    for attempt in range(1, max_retries + 1):
        logger.debug(f"Polling batch task status (attempt {attempt}/{max_retries})...")
        res = requests.get(result_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            logger.debug(
                f"Failed to get batch task result (status: {res.status_code}). Retrying..."
            )
            time.sleep(retry_interval)
            continue

        result = res.json()
        data = result.get("data", {})
        extract_results = data.get("extract_result", [])
        if not extract_results:
            logger.debug("No extract results yet. Retrying...")
            time.sleep(retry_interval)
            continue

        file_result = extract_results[0]
        state = file_result.get("state")
        logger.debug(f"Current file task state: {state}")
        if state == "done":
            logger.debug("File task completed successfully!")
            full_zip_url = file_result.get("full_zip_url")
            if not full_zip_url:
                raise Exception("No full_zip_url found in the task result!")
            return full_zip_url
        elif state == "failed":
            raise Exception("File parsing task failed! Check err_msg in the response.")

        time.sleep(retry_interval)
    raise TimeoutError("Batch task did not complete within the expected time.")


def download_and_extract_zip(zip_url):
    """
    Download the result ZIP file and extract its contents.
    Uses a persistent temporary directory (created with mkdtemp) so that
    the extracted folder remains available for further processing.
    """

    tmpdirname = tempfile.mkdtemp()
    zip_path = os.path.join(tmpdirname, "result.zip")
    logger.debug(f"Downloading ZIP file from: {zip_url}")
    r = requests.get(zip_url, stream=True, timeout=30)
    if r.status_code != 200:
        raise Exception(f"Failed to download ZIP file. Status: {r.status_code}")
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    logger.debug(f"ZIP file downloaded to: {zip_path}")

    extract_dir = os.path.join(tmpdirname, "extracted")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    logger.debug(f"ZIP file extracted to: {extract_dir}")
    return extract_dir


def extract_title_from_markdown(md_content):
    """
    Extract title from the markdown content by finding the first level-1 header.
    """
    for line in md_content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def demote_headers(md_text):
    # Convert h1 headings (# ) to h2 (## )
    return re.sub(r"^# (?!#)", "## ", md_text, flags=re.MULTILINE)


def generate_epub_from_extracted(extract_path, output_epub_path):
    """
    Generate an EPUB file from the extracted contents using pandoc.
    """
    logger.debug(f"Contents of extracted folder: {os.listdir(extract_path)}")
    md_path = os.path.join(extract_path, "full.md")
    if not os.path.exists(md_path):
        raise Exception("full.md not found in the extracted contents!")

    # Read and demote headers if necessary
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()
    # Demote h1 headings to h2 to avoid chapter splits when using --split-level=1
    md_text = demote_headers(md_text)

    # Write the modified markdown to a temporary file
    with tempfile.NamedTemporaryFile(
        "w+", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(md_text)
        tmp_md_path = tmp.name

    # Set up pandoc command with enhanced options
    pandoc_cmd = [
        "pandoc",
        tmp_md_path,
        "-o",
        output_epub_path,
        "--webtex=https://latex.codecogs.com/svg.latex?",
        "-f",
        "markdown_github+tex_math_single_backslash+tex_math_dollars",
        "--embed-resources",
        "--standalone",
        "--resource-path",
        extract_path,
        "--split-level=1",  # With no h1 headings, the document won't split into chapters.
        "--epub-title-page=false",  # otherwise it creates blank title chapter
    ]

    logger.debug(f"Running pandoc command: {' '.join(pandoc_cmd)}")
    result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
    logger.debug(f"Pandoc stdout for {output_epub_path}: {result.stdout}")
    logger.debug(f"Pandoc stderr for {output_epub_path}: {result.stderr}")

    if result.returncode != 0:
        error_msg = f"Pandoc failed with error: {result.stderr}"
        logger.error(error_msg)
        raise Exception(error_msg)

    logger.debug(f"EPUB file generated at: {output_epub_path}")
    # Optionally, remove the temporary markdown file
    os.remove(tmp_md_path)


def convert_pdf_to_epub(input_pdf_path, output_epub_path):
    """
    Convert a local PDF file into an EPUB file by:
      1. Requesting an upload URL from Mineru.
      2. Uploading the file.
      3. Polling for the parsing result.
      4. Downloading and extracting the result ZIP.
      5. Generating the EPUB.
    """
    logger.info(f"Converting PDF to EPUB: {input_pdf_path}")
    batch_id, file_urls = get_upload_url(input_pdf_path)
    if not file_urls or not isinstance(file_urls, list):
        raise Exception("No file upload URLs received.")
    upload_url = file_urls[0]

    upload_file(upload_url, input_pdf_path)
    logger.debug(f"File uploaded successfully.")

    full_zip_url = poll_batch_task_result(batch_id)

    extracted_path = download_and_extract_zip(full_zip_url)

    generate_epub_from_extracted(extracted_path, output_epub_path)


def process_pdf_for_conversion(pdf_path, epub_folder):
    """
    Convert a PDF to an EPUB if not already done.
    Returns the EPUB file path (located in epub_folder) on success;
    otherwise, returns the original PDF path.
    """
    base = os.path.basename(pdf_path)
    name, _ = os.path.splitext(base)
    epub_filename = name + ".epub"
    epub_path = os.path.join(epub_folder, epub_filename)
    if os.path.exists(epub_path):
        return epub_path
    try:
        convert_pdf_to_epub(pdf_path, epub_path)
        return epub_path
    except Exception as e:
        logger.error(f"Error converting PDF {pdf_path} to EPUB: {e}")
        return pdf_path


def process_epub_file(filename, article_folder, epub_folder):
    """
    Process an EPUB file in the epubArticles subdirectory.
    If the EPUB doesn't exist, tries to generate it from the corresponding PDF.

    Args:
        filename: The EPUB filename in the epubArticles subdirectory
        article_folder: The main article folder path
        epub_folder: The path to the epubArticles folder

    Returns:
        The path to the EPUB file if it exists or was generated, otherwise the original filename
    """
    epub_path = os.path.join(article_folder, filename)

    # If the epub doesn't exist, try to generate it from the original PDF
    if not os.path.exists(epub_path):
        # Get the corresponding PDF filename (same name but with .pdf extension)
        pdf_filename = os.path.splitext(os.path.basename(filename))[0] + ".pdf"
        pdf_path = os.path.join(article_folder, pdf_filename)

        # Check if the PDF exists
        if os.path.exists(pdf_path):
            # Use the existing function to convert the PDF to EPUB
            return process_pdf_for_conversion(pdf_path, epub_folder)
        else:
            logger.error(f"Original PDF not found for EPUB: {filename}")
            return filename
    return epub_path


# -------------------------------------------------------------------
# Existing functions for HTML/MHTML prefixing
# -------------------------------------------------------------------


def create_prefixed_html(original_path, prefixed_path, summary):
    """
    Create a copy of an HTML/MHTML file with summary prefixed as a <p> element.
    """
    try:
        with open(original_path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read()
        summary_html = f"<p>{summary}</p><br>"
        soup = BeautifulSoup(content, "html.parser")
        body = soup.find("body")
        if body:
            first_text_element = None
            for element in body.find_all(["p", "article", "section"]):
                text = element.get_text().strip()
                if (
                    text
                    and len(text) > 15
                    and any(char.isalpha() for char in text)
                    and sum(1 for char in text if char.isalpha()) > 5
                    and not text.startswith(("•", "-", "–", "—", "*", ">", "×"))
                ):
                    first_text_element = element
                    break
            if first_text_element:
                summary_soup = BeautifulSoup(summary_html, "html.parser")
                summary_elements = list(summary_soup.children)
                for element in reversed(summary_elements):
                    first_text_element.insert_before(element)
            modified_content = str(soup)
        else:
            raise Exception("No text tag found in HTML file")
        with open(prefixed_path, "w", encoding="utf-8") as file:
            file.write(modified_content)
        return True
    except Exception as e:
        logger.error(
            f"Error prefixing article {os.path.basename(original_path)}: {str(e)}"
        )
        return False


def process_article_for_prefixing(path, prefixed_folder):
    """
    For HTML/MHTML files, create a version with the summary prefixed.
    """
    logger.info(f"Processing article for prefixing: {path}")
    file_ext = os.path.splitext(path)[1].lower()
    if file_ext not in [".html", ".mhtml"]:
        return path
    filename = os.path.basename(path)
    article_data = db.get_article_by_file_name(filename)
    if not (article_data and article_data.get("summary")):
        return path
    prefixed_path = os.path.join(prefixed_folder, filename)
    if not os.path.exists(prefixed_path):
        success = create_prefixed_html(path, prefixed_path, article_data["summary"])
        if success:
            return prefixed_path
        return path
    else:
        return prefixed_path


# -------------------------------------------------------------------
# Main updateLists() integration with parallel processing
# -------------------------------------------------------------------


def appendToLists():
    config = getConfig()
    listToTagMappings = config["listToTagMappings"]

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
            listInfo.get("formats", config["docFormatsToMove"]),
            listInfo.get("prefixSummary", False),
        )
        if disabled:
            utils.deleteListIfExists(listName)
            continue

        logger.debug(f"Processing list {listName} with tags {listInfo}")
        articlePathsForList = db.searchArticlesByTags(
            all_tags=all_tags,
            any_tags=any_tags,
            not_any_tags=not_any_tags,
            readState=readState,
            formats=formats,
        )
        # Sorted list of full paths (extracted from dict items)
        articlePathsForList = [
            x[0] for x in sorted(articlePathsForList.items(), key=lambda x: x[1])
        ]
        # Initially add articles to the list
        utils.addArticlesToList(listName, articlePathsForList)


def modifyListFiles():
    config = getConfig()
    listToTagMappings = config["listToTagMappings"]

    for listName, listInfo in listToTagMappings.items():
        prefixSummary = listInfo.get("prefixSummary", False)
        # Retrieve the current list of article filenames
        list_articles = utils.getArticlesFromList(listName)
        # Ensure the EPUB subfolder exists
        article_folder = config["articleFileFolder"]
        epub_folder = os.path.join(article_folder, "epubArticles")
        os.makedirs(epub_folder, exist_ok=True)

        # For HTML/MHTML prefixing if enabled
        if prefixSummary:
            prefixed_folder = os.path.join(article_folder, "prefixedArticles")
            os.makedirs(prefixed_folder, exist_ok=True)
        else:
            prefixed_folder = None

        # Define helper function for processing a single article
        def process_single_article(filename):
            path = os.path.join(article_folder, filename)
            ext = os.path.splitext(path)[1].lower()
            if ext == ".epub":
                # Check if this is an epub file in the epubArticles subdirectory
                return process_epub_file(filename, article_folder, epub_folder)
            elif ext == ".pdf":
                logger.debug(f"Converting PDF to EPUB: {filename}")
                new_path = process_pdf_for_conversion(path, epub_folder)
                return new_path
            elif ext in [".html", ".mhtml"] and prefixSummary:
                new_path = process_article_for_prefixing(path, prefixed_folder)
                return new_path
            else:
                return path

        max_workers = 5  # pandoc uses a LOT of ram for conversion
        # Prepare a results list that preserves the order of list_articles
        updated_results = [None] * len(list_articles)
        logger.info(
            f"Processing {len(list_articles)} articles to add to list {listName}..."
        )
        remainingToComplete = len(list_articles)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(process_single_article, filename): i
                for i, filename in enumerate(list_articles)
            }
            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    updated_results[i] = future.result()
                    remainingToComplete -= 1
                    logger.debug(f"{remainingToComplete} articles remaining to process")
                except Exception as exc:
                    logger.error(f"Error processing {list_articles[i]}: {exc}")
                    updated_results[i] = list_articles[i]

        updated_article_paths = updated_results

        if updated_article_paths:
            utils.addArticlesToList(listName, updated_article_paths, overwrite=True)


if __name__ == "__main__":
    pass
