import os
import sqlite3
import json
import hashlib
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

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import utils
from src.utils import getConfig
from src.textExtraction import (
    extract_text_from_file,
    TextExtractionError,
    calculate_file_hash,
)

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


def summarize_with_openrouter(text: str) -> str:
    """Generate a summary of the text using OpenRouter API.

    Args:
        text: Text to summarize

    Returns:
        str: Generated summary
    """
    if not text or len(text.strip()) == 0:
        return "No text to summarize"

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    # Get configuration from config.json
    config = getConfig()
    model = config.get("ai_model", "openai/o3-mini")
    max_tokens = int(config.get("summary_out_max_tokens", 300))

    # Get optional referer info from environment variables
    referer = os.getenv("OPENROUTER_REFERER", "articleSearchAndSync")
    title = os.getenv("OPENROUTER_TITLE", "Article Search and Sync")

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": referer,
                "X-Title": title,
            },
        )

        print(f"Sending summary request to OpenRouter with model: {model}")

        system_prompt = "You are a helpful system that generates concise summaries of academic or educational content."
        user_prompt = f"""Please summarize the following text in a concise but informative way that captures the main points, topics, concepts, novel arguments, novel ideas, and important details. The summary should be written from the same perspective as the article i.e. first person.

Text to summarize:
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

        # Extract the summary from the response
        summary = response.choices[0].message.content
        return summary.strip()

    except Exception as e:
        error_message = f"Error generating summary: {str(e)}"
        error_traceback = traceback.format_exc()
        print(error_message)
        traceback.print_exc()
        return f"Failed to generate summary: {error_message}"


def get_article_summary(file_path: str) -> str:
    """Get or create a summary for an article.

    Args:
        file_path: Path to the article file

    Returns:
        str: Article summary
    """
    # Calculate file hash
    file_hash = calculate_file_hash(file_path)
    file_name = os.path.basename(file_path)
    file_format = os.path.splitext(file_path)[1].lower()

    # Setup database
    db_path = setup_database()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if summary exists
    cursor.execute(
        "SELECT summary FROM article_summaries WHERE file_hash = ?", (file_hash,)
    )
    result = cursor.fetchone()

    if result:
        summary = result[0]
        conn.close()
        return summary

    # Extract text from the file
    try:
        config = getConfig()
        max_words = int(config.get("summary_in_max_words", 3000))

        text, extraction_method, word_count = extract_text_from_file(
            file_path, max_words
        )

        # Generate a summary
        summary = summarize_with_openrouter(text)

        # Store the summary
        cursor.execute(
            """
            INSERT INTO article_summaries 
            (file_hash, file_name, file_format, summary, extraction_method, word_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_hash, file_name, file_format, summary, extraction_method, word_count),
        )

        conn.commit()
        conn.close()

        return summary

    except Exception as e:
        error_message = f"Error summarizing article: {str(e)}"
        error_traceback = traceback.format_exc()
        print(error_message)
        traceback.print_exc()
        conn.close()
        return f"Failed to summarize article: {error_message}"


def summarize_articles(articles_path: Optional[str] = None) -> None:
    """Summarize all supported articles in the given path that don't have summaries yet.
    Uses parallel processing to summarize multiple articles simultaneously.

    Args:
        articles_path: Path to the articles directory
    """
    if not articles_path:
        # Get the default articles directory from config
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")
        if not articles_path:
            print("No articles directory specified in config or as argument")
            return

    # Make path absolute if it's not already
    if not os.path.isabs(articles_path):
        articles_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), articles_path
        )

    # Set up the database
    db_path = setup_database()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of all supported articles
    supported_extensions = [
        ".pdf",
        ".html",
        ".htm",
        ".mhtml",
        ".mht",
        ".epub",
        ".mobi",
        ".txt",
        ".md",
    ]
    all_articles = []

    for root, _, files in os.walk(articles_path):
        for file in files:
            if any(file.lower().endswith(ext) for ext in supported_extensions):
                file_path = os.path.join(root, file)
                all_articles.append(file_path)

    print(f"Found {len(all_articles)} supported articles")

    # Get list of articles already summarized
    cursor.execute("SELECT file_hash FROM article_summaries")
    summarized_hashes = {row[0] for row in cursor.fetchall()}
    conn.close()

    # Filter out articles that already have summaries
    articles_to_summarize = []
    for article_path in all_articles:
        try:
            file_hash = calculate_file_hash(article_path)
            if file_hash not in summarized_hashes:
                articles_to_summarize.append(article_path)
        except Exception as e:
            print(f"Error calculating hash for {article_path}: {str(e)}")

    print(f"{len(articles_to_summarize)} articles need summarization")

    if not articles_to_summarize:
        print("No new articles to summarize")
        return

    # Get max workers from config
    config = getConfig()
    max_workers = int(config.get("max_workers", 4))

    # Get max summaries per session from config
    max_summaries_per_session = int(config.get("maxSummariesPerSession", 150))

    # Limit the number of articles to process based on maxSummariesPerSession
    if len(articles_to_summarize) > max_summaries_per_session:
        print(
            f"Limiting to {max_summaries_per_session} articles due to maxSummariesPerSession config setting"
        )
        articles_to_summarize = articles_to_summarize[:max_summaries_per_session]

    # Use ThreadPoolExecutor to process multiple articles in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all articles for processing
        future_to_article = {
            executor.submit(process_single_article, article_path): article_path
            for article_path in articles_to_summarize
        }

        # Process results as they complete
        for i, future in enumerate(concurrent.futures.as_completed(future_to_article)):
            article_path = future_to_article[future]
            try:
                success, message = future.result()
                status = "Success" if success else "Failed"
                print(
                    f"[{i+1}/{len(articles_to_summarize)}] {status}: {os.path.basename(article_path)} - {message}"
                )
            except Exception as e:
                print(
                    f"[{i+1}/{len(articles_to_summarize)}] Exception: {os.path.basename(article_path)} - {str(e)}"
                )
                traceback.print_exc()


def process_single_article(article_path: str) -> Tuple[bool, str]:
    """Process a single article for summarization.

    Args:
        article_path: Path to the article file

    Returns:
        Tuple[bool, str]: Success status and result message
    """
    try:
        summary = get_article_summary(article_path)
        if summary.startswith("Failed to summarize article:"):
            return False, summary
        return True, f"Summary generated ({len(summary)} chars)"
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        traceback.print_exc()
        return False, error_message


if __name__ == "__main__":
    summarize_articles(None)
