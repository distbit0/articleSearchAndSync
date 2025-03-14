import os
import sqlite3
import json
import hashlib
import re
import traceback
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import tempfile
import pysnooper
import subprocess
from dotenv import load_dotenv
from openai import OpenAI
import concurrent.futures

# Import utils properly based on how it's structured in the project
import sys

from pydantic import SnowflakeDsn

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import utils
from src.utils import getConfig

# Load environment variables from the correct path
# Try multiple potential locations for the .env file
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
potential_env_paths = [
    os.path.join(project_root, ".env"),
    os.path.join(os.getcwd(), ".env"),
    os.path.abspath(".env"),
]

for env_path in potential_env_paths:
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        print(f"Loaded environment from: {env_path}")
        break


class TextExtractionError(Exception):
    """Custom exception for text extraction errors."""

    pass


def setup_database() -> str:
    """Setup the SQLite database for article summaries if it doesn't exist.

    Returns:
        str: Path to the database file
    """
    storage_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage"
    )
    os.makedirs(storage_dir, exist_ok=True)
    db_path = os.path.join(storage_dir, "article_summaries.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS article_summaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_hash TEXT UNIQUE,
        file_name TEXT,
        file_format TEXT,
        summary TEXT,
        extraction_method TEXT,
        word_count INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    conn.commit()
    conn.close()
    return db_path


def calculate_file_hash(file_path: str) -> str:
    """Calculate a hash for the file to uniquely identify it.

    Args:
        file_path: Path to the file

    Returns:
        str: Hexadecimal hash of the file
    """
    # Reusing the existing file hash function from importLinks.py
    hasher = hashlib.sha256()
    file_size = os.path.getsize(file_path)

    if file_size < 4096:
        with open(file_path, "rb") as f:
            hasher.update(f.read())
    else:
        offset = (file_size - 4096) // 2
        with open(file_path, "rb") as f:
            f.seek(offset)
            hasher.update(f.read(4096))

    return hasher.hexdigest()


def run_command(cmd: List[str], timeout: int = 60) -> Tuple[bool, str]:
    """Run a command with timeout and return success status and output.

    Args:
        cmd: Command and arguments as a list
        timeout: Maximum execution time in seconds

    Returns:
        Tuple[bool, str]: Success status and command output/error
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, f"Error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, f"Command timed out after {timeout} seconds: {' '.join(cmd)}"
    except Exception as e:
        return False, f"Exception running command: {str(e)}"


def extract_text_from_pdf(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from a PDF file using multiple methods.

    Args:
        file_path: Path to the PDF file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    extraction_methods = [
        ("pdftotext", extract_pdf_with_pdftotext),
        ("PyPDF2", extract_pdf_with_pypdf2),
        ("utils.getPdfText", extract_pdf_with_utils),
    ]

    errors = []
    for method_name, method_func in extraction_methods:
        try:
            text = method_func(file_path)
            if text and len(text.strip()) > 0:
                # Clean the text
                text = clean_text(text)
                words = text.split()
                word_count = len(words)

                if max_words is not None and word_count > max_words:
                    text = " ".join(words[:max_words])
                    word_count = max_words

                return text, method_name, word_count
            else:
                errors.append(f"{method_name}: Empty text")
        except Exception as e:
            errors.append(f"{method_name}: {str(e)}")

    error_msg = "\n".join(errors)
    raise TextExtractionError(
        f"All PDF extraction methods failed for {file_path}:\n{error_msg}"
    )


def extract_pdf_with_pdftotext(file_path: str) -> str:
    """Extract text from PDF using pdftotext command (from poppler-utils).

    Args:
        file_path: Path to the PDF file

    Returns:
        str: Extracted text
    """
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
        temp_path = temp.name

    success, output = run_command(["pdftotext", "-layout", file_path, temp_path])

    if not success:
        os.unlink(temp_path)
        raise TextExtractionError(f"pdftotext failed: {output}")

    with open(temp_path, "r", errors="replace") as f:
        text = f.read()

    os.unlink(temp_path)
    return text


def extract_pdf_with_pypdf2(file_path: str) -> str:
    """Extract text from PDF using PyPDF2 library.

    Args:
        file_path: Path to the PDF file

    Returns:
        str: Extracted text
    """
    import PyPDF2

    text = ""
    with open(file_path, "rb") as file:
        pdf_reader = PyPDF2.PdfReader(file)
        num_pages = len(pdf_reader.pages)

        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n\n"

    return text


def extract_pdf_with_utils(file_path: str) -> str:
    """Extract text from PDF using the existing utils.getPdfText function.

    Args:
        file_path: Path to the PDF file

    Returns:
        str: Extracted text
    """
    return utils.getPdfText(file_path)


def extract_text_from_html(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from an HTML or MHTML file using multiple methods.

    Args:
        file_path: Path to the HTML file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    extraction_methods = [
        ("html2text", extract_html_with_html2text),
        ("beautifulsoup", extract_html_with_bs4),
        ("regex", extract_html_with_regex),
    ]

    errors = []
    for method_name, method_func in extraction_methods:
        try:
            text = method_func(file_path)
            if text and len(text.strip()) > 0:
                # Clean the text
                text = clean_text(text)
                words = text.split()
                word_count = len(words)

                if max_words is not None and word_count > max_words:
                    text = " ".join(words[:max_words])
                    word_count = max_words

                return text, method_name, word_count
            else:
                errors.append(f"{method_name}: Empty text")
        except Exception as e:
            errors.append(f"{method_name}: {str(e)}")

    error_msg = "\n".join(errors)
    raise TextExtractionError(
        f"All HTML extraction methods failed for {file_path}:\n{error_msg}"
    )


def extract_html_with_html2text(file_path: str) -> str:
    """Extract text from HTML using html2text command.

    Args:
        file_path: Path to the HTML file

    Returns:
        str: Extracted text
    """
    success, output = run_command(["html2text", "-utf8", file_path])

    if not success:
        raise TextExtractionError(f"html2text failed: {output}")

    return output


def extract_html_with_bs4(file_path: str) -> str:
    """Extract text from HTML using BeautifulSoup.

    Args:
        file_path: Path to the HTML file

    Returns:
        str: Extracted text
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("BeautifulSoup4 is required for HTML extraction.")

    with open(file_path, "r", errors="replace") as file:
        soup = BeautifulSoup(file.read(), "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()

        # Get text
        text = soup.get_text(separator=" ")

        # Remove excessive whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text


def extract_html_with_regex(file_path: str) -> str:
    """Extract text from HTML using regex.

    Args:
        file_path: Path to the HTML file

    Returns:
        str: Extracted text
    """
    with open(file_path, "r", errors="replace") as file:
        content = file.read()

        # Remove script and style elements
        content = re.sub(r"<script.*?>.*?</script>", " ", content, flags=re.DOTALL)
        content = re.sub(r"<style.*?>.*?</style>", " ", content, flags=re.DOTALL)

        # Remove HTML tags
        content = re.sub(r"<[^>]+>", " ", content)

        # Decode HTML entities
        content = re.sub(r"&nbsp;", " ", content)
        content = re.sub(r"&amp;", "&", content)
        content = re.sub(r"&lt;", "<", content)
        content = re.sub(r"&gt;", ">", content)
        content = re.sub(r"&quot;", '"', content)
        content = re.sub(r"&#39;", "'", content)

        # Clean up whitespace
        content = re.sub(r"\s+", " ", content)

        return content.strip()


def extract_text_from_epub(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from an EPUB file using multiple methods.

    Args:
        file_path: Path to the EPUB file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    extraction_methods = [
        ("calibre", extract_epub_with_calibre),
        ("epub2text", extract_epub_with_epub2txt),
    ]

    errors = []
    for method_name, method_func in extraction_methods:
        try:
            text = method_func(file_path)
            if text and len(text.strip()) > 0:
                # Clean the text
                text = clean_text(text)
                words = text.split()
                word_count = len(words)

                if max_words is not None and word_count > max_words:
                    text = " ".join(words[:max_words])
                    word_count = max_words

                return text, method_name, word_count
            else:
                errors.append(f"{method_name}: Empty text")
        except Exception as e:
            errors.append(f"{method_name}: {str(e)}")

    error_msg = "\n".join(errors)
    raise TextExtractionError(
        f"All EPUB extraction methods failed for {file_path}:\n{error_msg}"
    )


def extract_epub_with_calibre(file_path: str) -> str:
    """Extract text from EPUB using calibre's ebook-convert.

    Args:
        file_path: Path to the EPUB file

    Returns:
        str: Extracted text
    """
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
        temp_path = temp.name

    success, output = run_command(["ebook-convert", file_path, temp_path])

    if not success:
        os.unlink(temp_path)
        raise TextExtractionError(f"ebook-convert failed: {output}")

    with open(temp_path, "r", errors="replace") as f:
        text = f.read()

    os.unlink(temp_path)
    return text


def extract_epub_with_epub2txt(file_path: str) -> str:
    """Extract text from EPUB using epub2txt command.

    Args:
        file_path: Path to the EPUB file

    Returns:
        str: Extracted text
    """
    success, output = run_command(["epub2txt", file_path])

    if not success:
        raise TextExtractionError(f"epub2txt failed: {output}")

    return output


def extract_text_from_mobi(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from a MOBI file.

    Args:
        file_path: Path to the MOBI file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp:
            temp_path = temp.name

        success, output = run_command(["ebook-convert", file_path, temp_path])

        if not success:
            os.unlink(temp_path)
            raise TextExtractionError(f"ebook-convert failed for MOBI: {output}")

        with open(temp_path, "r", errors="replace") as f:
            text = f.read()

        os.unlink(temp_path)

        # Clean the text
        text = clean_text(text)
        words = text.split()
        word_count = len(words)

        if max_words is not None and word_count > max_words:
            text = " ".join(words[:max_words])
            word_count = max_words

        return text, "ebook-convert", word_count

    except Exception as e:
        raise TextExtractionError(f"MOBI extraction failed: {str(e)}")


def clean_text(text: str) -> str:
    """Clean extracted text.

    Args:
        text: Raw extracted text

    Returns:
        str: Cleaned text
    """
    # Replace multiple newlines with a single newline
    text = re.sub(r"\n+", "\n", text)

    # Replace multiple spaces with a single space
    text = re.sub(r"\s+", " ", text)

    # Replace Unicode control characters
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Replace common OCR errors
    text = re.sub(
        r"(?<=[a-z])l(?=[a-z])", "i", text
    )  # Replace 'l' with 'i' in middle of words

    return text.strip()


def extract_text_from_file(
    file_path: str, max_words: int = None
) -> Tuple[str, str, int]:
    """Extract text from a file based on its format.

    Args:
        file_path: Path to the file
        max_words: Maximum number of words to extract

    Returns:
        Tuple[str, str, int]: Extracted text, method used, word count
    """
    file_format = file_path.split(".")[-1].lower() if "." in file_path else ""

    # Get max_words from config if not specified
    if max_words is None:
        config = getConfig()
        max_words = int(config.get("summary_in_max_words", 10000))

    try:
        if file_format == "pdf":
            return extract_text_from_pdf(file_path, max_words)
        elif file_format in ["html", "mhtml"]:
            return extract_text_from_html(file_path, max_words)
        elif file_format == "epub":
            return extract_text_from_epub(file_path, max_words)
        elif file_format == "mobi":
            return extract_text_from_mobi(file_path, max_words)
        else:
            raise TextExtractionError(f"Unsupported file format: {file_format}")
    except Exception as e:
        traceback.print_exc()
        raise TextExtractionError(f"Text extraction failed: {str(e)}")


def summarize_with_openrouter(text: str) -> str:
    """Generate a summary of the text using OpenRouter API.

    Args:
        text: Text to summarize

    Returns:
        str: Generated summary
    """
    if not text:
        return "Could not extract text from the document."

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    # Get configuration from config.json
    config = getConfig()
    model = config.get("ai_model", "openai/o3-mini")

    # Get the target summary word count directly from config
    target_word_count = int(config.get("summary_max_words", 150))

    # Get optional referer info from environment variables
    referer = os.getenv("OPENROUTER_REFERER", "articleSearchAndSync")
    title = os.getenv("OPENROUTER_TITLE", "Article Search and Sync")

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        print(f"Sending request to OpenRouter with model: {model}")

        # Set a high max_tokens to prevent truncation
        max_tokens = 2000  # Much higher than needed to prevent any truncation

        # First attempt at summarization
        system_prompt = (
            "You are a precise document summarizer that extracts key points from text."
        )
        user_prompt = f"""Please summarize the following document. Your summary should:
1. Be approximately {target_word_count} words (not more than {target_word_count + 50} words)
2. Focus on extracting the main points, arguments and concepts
3. Be well-structured
4. Maintain the original intent of the document

Document:
{text}"""

        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": referer,
                "X-Title": title,
            },
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
        )

        summary = response.choices[0].message.content
        word_count = len(summary.split())

        print(f"Initial summary word count: {word_count}")

        # If the summary is too long, ask the model to condense it
        if word_count > target_word_count + 50:
            print(
                f"Summary too long ({word_count} words). Requesting condensed version..."
            )

            condense_prompt = f"""Your summary is {word_count} words, which exceeds the requested {target_word_count} word limit. 
Please condense this summary to be approximately {target_word_count} words while preserving the most important information:

{summary}"""

            response = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": referer,
                    "X-Title": title,
                },
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": summary},
                    {"role": "user", "content": condense_prompt},
                ],
                max_tokens=max_tokens,
            )

            summary = response.choices[0].message.content
            word_count = len(summary.split())
            print(f"Condensed summary word count: {word_count}")

        return summary
    except Exception as e:
        print(f"Error with OpenRouter API: {e}")
        traceback.print_exc()


def get_article_summary(file_path: str) -> str:
    """Get or create a summary for an article.

    Args:
        file_path: Path to the article file

    Returns:
        str: Article summary
    """
    db_path = setup_database()
    file_hash = calculate_file_hash(file_path)
    file_name = os.path.basename(file_path)
    file_format = file_path.split(".")[-1].lower() if "." in file_path else ""

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if we already have a summary for this file
    cursor.execute(
        "SELECT summary FROM article_summaries WHERE file_hash = ?", (file_hash,)
    )
    existing_summary = cursor.fetchone()

    if existing_summary:
        conn.close()
        return existing_summary[0]

    # Extract text from the file
    config = getConfig()
    max_words = int(config.get("summary_in_max_words", 10000))

    try:
        text, extraction_method, word_count = extract_text_from_file(
            file_path, max_words
        )

        # Generate a summary
        try:
            summary = summarize_with_openrouter(text)

            # Check if summary was generated successfully
            if summary is None or summary.startswith("Error:"):
                print(f"Warning: Failed to generate summary for {file_name}: {summary}")
                conn.close()
                return f"Failed to generate summary: {summary}"
        except Exception as sum_error:
            print(f"Error during summary generation: {sum_error}")
            conn.close()
            return f"Error during summary generation: {str(sum_error)}"

        # Only store successful summaries in the database
        print("Storing summary in database...", summary)
        cursor.execute(
            "INSERT INTO article_summaries (file_hash, file_name, file_format, summary, extraction_method, word_count) VALUES (?, ?, ?, ?, ?, ?)",
            (file_hash, file_name, file_format, summary, extraction_method, word_count),
        )

        conn.commit()
        conn.close()

        return summary
    except TextExtractionError as e:
        # Log the error but don't store it in the database
        error_message = f"Failed to extract text: {str(e)}"
        print(error_message)

        conn.close()
        return error_message


def summarize_articles(articles_path: Optional[str] = None) -> None:
    """Summarize all supported articles in the given path that don't have summaries yet.
    Uses parallel processing to summarize multiple articles simultaneously.

    Args:
        articles_path: Path to the articles directory
    """
    if not articles_path:
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")

    if not articles_path:
        print("No articles path specified.")
        return

    # Check if OpenRouter API key is set
    api_key = os.getenv("OPENROUTER_API_KEY")
    print(f"API Key found: {'Yes' if api_key else 'No'}")

    # Only check if it's completely missing, not if it has a specific value
    if not api_key:
        print(
            "OpenRouter API key not found. Please set OPENROUTER_API_KEY in the .env file."
        )
        return

    # Get supported formats from the config
    config = getConfig()
    supported_formats = config.get("docFormatsToMove", [])

    # Get parallel batch size from config (default to 4 if not specified)
    batch_size = int(config.get("summary_batch_size", 4))
    print(f"Using batch size of {batch_size} for parallel summarization")

    # Get maximum summaries per session from config (default to 100 if not specified)
    max_summaries_per_session = int(config.get("maxSummariesPerSession", 100))
    print(f"Will process up to {max_summaries_per_session} articles per session")

    # Get all articles with the supported formats
    print(
        f"Searching for articles in {articles_path} with formats: {supported_formats}"
    )
    articles = utils.searchArticlesForQuery(
        "*", formats=supported_formats, path=articles_path
    )

    print(f"Found {len(articles)} articles to potentially summarize")

    # Setup the database
    db_path = setup_database()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all already processed file hashes
    cursor.execute("SELECT file_hash FROM article_summaries")
    processed_hashes = {row[0] for row in cursor.fetchall()}

    conn.close()

    # Filter articles that haven't been summarized yet
    articles_to_process = []
    for article_path in articles:
        file_hash = calculate_file_hash(article_path)
        if file_hash in processed_hashes:
            print(f"Article already summarized: {os.path.basename(article_path)}")
        else:
            articles_to_process.append(article_path)

    print(f"Found {len(articles_to_process)} articles to summarize")

    # Respect the maxSummariesPerSession limit
    if len(articles_to_process) > max_summaries_per_session:
        print(
            f"Limiting to {max_summaries_per_session} articles as per maxSummariesPerSession config"
        )
        articles_to_process = articles_to_process[:max_summaries_per_session]

    # Process articles in parallel batches
    with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
        # Submit all articles for processing
        future_to_article = {
            executor.submit(process_single_article, article_path): article_path
            for article_path in articles_to_process
        }

        # Process completed futures as they complete
        for future in concurrent.futures.as_completed(future_to_article):
            article_path = future_to_article[future]
            try:
                success, message = future.result()
                if success:
                    print(
                        f"✅ Successfully summarized: {os.path.basename(article_path)} - {message}"
                    )
                else:
                    print(
                        f"❌ Failed to summarize: {os.path.basename(article_path)} - {message}"
                    )
            except Exception as e:
                print(f"❌ Error processing {os.path.basename(article_path)}: {e}")
                traceback.print_exc()

    print("Article summarization complete")


def process_single_article(article_path: str) -> Tuple[bool, str]:
    """Process a single article for summarization.

    Args:
        article_path: Path to the article file

    Returns:
        Tuple[bool, str]: Success status and result message
    """
    try:
        print(f"Starting summarization of: {os.path.basename(article_path)}")
        summary = get_article_summary(article_path)
        return True, f"Summary generated ({len(summary)} characters)"
    except Exception as e:
        return False, str(e)


if __name__ == "__main__":
    # Test the summarization functionality
    summarize_articles()
