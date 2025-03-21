import sqlite3
import random
import traceback
from pathlib import Path
from typing import Optional, Tuple
import concurrent.futures
import sys
from loguru import logger
from dotenv import load_dotenv
from openai import OpenAI
import os

# Import utils properly based on how it's structured in the project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils import getConfig, getArticlePathsForQuery
from src.textExtraction import (
    extract_text_from_file,
    TextExtractionError,
    calculate_file_hash,
)

# Configure loguru logger
log_file_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "summary.log",
)
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Remove default handler and add custom handlers
logger.remove()
# Add stdout handler
logger.add(sys.stdout, level="INFO")
# Add rotating file handler - 5MB max size, keep 3 backup files
logger.add(
    log_file_path,
    rotation="5 MB",
    retention=3,
    level="WARNING",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
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
        logger.debug(f"Loaded environment from: {env_path}")
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


def summarize_with_openrouter(text: str) -> Tuple[str, bool]:
    """Generate a summary of the text using OpenRouter API.

    Args:
        text: Text to summarize

    Returns:
        Tuple[str, bool]: Generated summary and flag indicating if text was sufficient (True) or insufficient (False)
    """
    if not text or len(text.strip()) == 0:
        logger.warning("No text to summarize")
        return "No text to summarize", False

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not found in environment variables")
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

        logger.debug(f"Sending summary request to OpenRouter with model: {model}")

        system_prompt = """You are a helpful system that generates concise summaries of academic or educational content. 
You must first assess if the provided text contains sufficient content to generate a meaningful summary. 
If the text is too short, fragmented, or lacks substantive content, respond with "[INSUFFICIENT_TEXT]" at the beginning of your response. DO NOT respond with [INSUFFICIENT_TEXT] if there is substantive content but the text merely ends abruptly/not at the end of a sentence."""

        user_prompt = f"""Please analyze the following text:

{text}

First, determine if the text provides enough substantial content to write a meaningful summary. 
If the text is too short, fragmented, or clearly not the full article (e.g., just metadata, table of contents, or a small snippet), 
respond with "[INSUFFICIENT_TEXT]" followed by a brief explanation of why the text is insufficient.

If the text IS sufficient, please summarize it in a concise but informative way that captures the main points, topics, concepts, 
novel arguments, novel ideas, and important details. The summary should be written from the same perspective as the article i.e. first person."""

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

        # Check if the summary indicates insufficient text
        if summary.strip().startswith("[INSUFFICIENT_TEXT]"):
            logger.warning(f"Insufficient text detected: {summary.strip()}")
            return summary.strip(), False

        return summary.strip(), True

    except Exception as e:
        error_message = f"Error generating summary: {str(e)}"
        error_traceback = traceback.format_exc()
        logger.error(f"{error_message}\n{error_traceback}")
        traceback.print_exc()
        return f"Failed to generate summary: {error_message}", False


def get_article_summary(file_path: str) -> Tuple[str, bool]:
    """Get or create a summary for an article.

    Args:
        file_path: Path to the article file

    Returns:
        Tuple[str, bool]: Article summary and a flag indicating if text was sufficient
    """
    # Calculate file hash
    file_hash = calculate_file_hash(file_path)
    file_name = os.path.basename(file_path)
    file_format = os.path.splitext(file_path)[1].lower()
    if file_format.startswith("."):
        file_format = file_format[1:]  # Remove leading dot

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

        # If summary is NULL, it means the file was added to the database but not yet summarized
        if summary is None:
            logger.debug(
                f"File {file_name} is in the database but has not been summarized yet"
            )
            # Close the current connection since we'll open a new one during summarization
            conn.close()
            # Proceed with summarization (same logic as below)
        else:
            conn.close()
            # Check if summary indicates insufficient text (empty string)
            is_sufficient = bool(
                summary
            )  # Empty string means insufficient, anything else is sufficient
            return summary, is_sufficient
    else:
        # Article not in database, so no existing summary
        conn.close()

    # Extract text from the file
    try:
        config = getConfig()
        max_words = int(config.get("summary_in_max_words", 3000))

        text, extraction_method, word_count = extract_text_from_file(
            file_path, max_words
        )

        # Generate a summary and check if text was sufficient
        summary, is_sufficient = summarize_with_openrouter(text)

        # Reconnect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the article is already in the database (could have been added by add_files_to_database)
        cursor.execute(
            "SELECT id FROM article_summaries WHERE file_hash = ?", (file_hash,)
        )
        existing_article = cursor.fetchone()

        # If text is insufficient, set summary to empty string
        if not is_sufficient:
            db_summary = ""
            logger.warning(
                f"Insufficient text for summary in file: {file_path}, storing empty summary"
            )
        else:
            db_summary = summary
            logger.debug(f"Successfully created summary for file: {file_path}")

        if existing_article:
            # Update existing record
            cursor.execute(
                """
                UPDATE article_summaries
                SET summary = ?, extraction_method = ?, word_count = ?
                WHERE file_hash = ?
                """,
                (db_summary, extraction_method, word_count, file_hash),
            )
            logger.debug(f"Updated existing database entry for file: {file_path}")
        else:
            # Insert new record
            cursor.execute(
                """
                INSERT INTO article_summaries 
                (file_hash, file_name, file_format, summary, extraction_method, word_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    file_hash,
                    file_name,
                    file_format,
                    db_summary,
                    extraction_method,
                    word_count,
                ),
            )
            logger.debug(f"Created new database entry for file: {file_path}")

        conn.commit()
        conn.close()

        if not is_sufficient:
            logger.warning(
                f"Stored empty summary for file with insufficient text: {file_path}"
            )
        else:
            logger.debug(
                f"Successfully created and stored summary for file: {file_path}"
            )

        return summary, is_sufficient

    except Exception as e:
        error_message = f"Error summarizing article: {str(e)}"
        error_traceback = traceback.format_exc()
        logger.error(f"{error_message}\n{error_traceback}")
        traceback.print_exc()

        # Ensure the database connection is closed in case of error
        try:
            conn.close()
        except:
            pass

        return f"Failed to summarize article: {error_message}", False


def summarize_articles(articles_path: Optional[str] = None, query: str = "*") -> None:
    """Summarize all supported articles in the given path that don't have summaries yet.
    Uses parallel processing to summarize multiple articles simultaneously.

    Args:
        articles_path: Path to the articles directory
        query: Query string to filter articles (default: "*" for all articles)
    """
    if not articles_path:
        # Get the default articles directory from config
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")
        if not articles_path:
            logger.error("No articles directory specified in config or as argument")
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

    # Get list of articles that need summarization (NULL summary)
    cursor.execute(
        """
        SELECT file_hash, file_name
        FROM article_summaries
        WHERE summary IS NULL
    """
    )
    articles_needing_summary = cursor.fetchall()
    conn.close()

    logger.info(
        f"Found {len(articles_needing_summary)} articles in database that need summarization"
    )

    if not articles_needing_summary:
        logger.info("No articles need summarization")
        return

    # Articles to summarize, with their paths
    articles_to_summarize = []

    # Get max summaries per session from config before the loop
    config = getConfig()
    max_summaries_per_session = int(config.get("maxSummariesPerSession", 150))

    # Process each article that needs summarization
    random.shuffle(articles_needing_summary)

    for file_hash, file_name in articles_needing_summary:
        # Stop if we've reached the maximum number of articles to summarize
        if len(articles_to_summarize) >= max_summaries_per_session:
            logger.info(
                f"Reached limit of {max_summaries_per_session} articles, stopping search"
            )
            break

        # Find the article path using the helper function
        file_paths = getArticlePathsForQuery("*", [], articles_path, file_name)

        if file_paths:
            # Use the first matching file path
            articles_to_summarize.append(file_paths[0])
        else:
            logger.warning(
                f"Could not find file path for {file_name} in {articles_path}"
            )

    logger.info(f"{len(articles_to_summarize)} articles need summarization")

    if not articles_to_summarize:
        logger.info("No articles to summarize")
        return

    # Get max workers from config
    config = getConfig()
    max_workers = int(config.get("llm_api_batch_size", 4))

    # Track statistics
    total_articles = len(articles_to_summarize)
    successful = 0
    failed = 0
    insufficient = 0

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
                success, message, is_sufficient = future.result()
                file_name = os.path.basename(article_path)

                if success:
                    if is_sufficient:
                        logger.debug(
                            f"Successfully summarized: {article_path} - {message}"
                        )
                        successful += 1
                    else:
                        logger.warning(
                            f"Insufficient text in: {article_path} - storing empty summary"
                        )
                        insufficient += 1
                else:
                    logger.error(f"Failed to summarize: {article_path} - {message}")
                    failed += 1
            except Exception as e:
                file_name = os.path.basename(article_path)
                logger.error(
                    f"Unexpected error processing {article_path}: {str(e)}\n{traceback.format_exc()}"
                )
                failed += 1

    logger.info(
        f"Summary: Processed {total_articles} articles - {successful} successful, {insufficient} insufficient text, {failed} failed"
    )


def process_single_article(article_path: str) -> Tuple[bool, str, bool]:
    """Process a single article for summarization.

    Args:
        article_path: Path to the article file

    Returns:
        Tuple[bool, str, bool]: Success status, result message, and flag indicating if text was sufficient
    """
    try:
        summary, is_sufficient = get_article_summary(article_path)
        if summary.startswith("Failed to summarize article:"):
            return False, summary, False

        if not is_sufficient:
            return True, f"Insufficient text detected ({len(summary)} chars)", False

        return True, f"Summary generated ({len(summary)} chars)", True
    except Exception as e:
        error_message = f"Error processing article: {str(e)}"
        logger.error(f"{error_message}\n{traceback.format_exc()}")
        return False, error_message, False


def add_files_to_database(articles_path: Optional[str] = None) -> int:
    """Add all supported files to the database without summarizing.

    This function finds all article files in the given path and adds them to the database
    with NULL summaries, indicating they need to be summarized later. This ensures that
    folder tagging can work with all files regardless of summarization status.

    Args:
        articles_path: Path to the articles directory

    Returns:
        int: Number of new files added to the database
    """
    # Get articles path from config if not provided
    if not articles_path:
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")
        if not articles_path:
            logger.error("Article file folder not found in config")
            return 0

    logger.debug(f"Adding files to database from: {articles_path}")

    # Setup database
    db_path = setup_database()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of supported file formats from config
    config = getConfig()
    supported_formats = config.get(
        "docFormatsToMove", ["pdf", "djvu", "epub", "mobi", "html", "mhtml"]
    )
    file_names_to_skip = config.get("fileNamesToSkip", [])

    # Get all existing file hashes to avoid duplicates
    cursor.execute("SELECT file_hash FROM article_summaries")
    existing_hashes = set(row[0] for row in cursor.fetchall())

    # Add all files to database with NULL summary
    added_count = 0

    # Use getArticlePathsForQuery to find all articles with supported formats in one call
    all_article_paths = getArticlePathsForQuery("*", supported_formats, articles_path)
    logger.info(f"Found {len(all_article_paths)} files in {articles_path}.")

    # Process each file found
    for file_path in all_article_paths:
        file_name = os.path.basename(file_path)

        # Skip files in the exclusion list
        if file_name in file_names_to_skip:
            continue

        try:
            # Calculate file hash to check if already in DB
            file_hash = calculate_file_hash(file_path)

            # Skip if already in database
            if file_hash in existing_hashes:
                continue

            # Determine the file format from the extension
            file_ext = os.path.splitext(file_name)[1].lstrip(".")

            # Add to database with NULL summary
            # We use NULL (not empty string) to indicate it needs to be summarized
            # This is different from an empty string ("") which indicates a failed summarization
            cursor.execute(
                """
                INSERT INTO article_summaries 
                (file_hash, file_name, file_format, summary, extraction_method, word_count)
                VALUES (?, ?, ?, NULL, NULL, 0)
                """,
                (file_hash, file_name, file_ext),
            )
            existing_hashes.add(file_hash)
            added_count += 1

            if added_count % 100 == 0:
                logger.debug(f"Added {added_count} new files to database")
                conn.commit()  # Commit in batches

        except Exception as e:
            logger.error(f"Error adding file to database: {file_path}: {str(e)}")
            traceback.print_exc()

    # Final commit
    conn.commit()
    conn.close()

    logger.info(f"Added a total of {added_count} new files to database")
    return added_count


if __name__ == "__main__":
    add_files_to_database()
    summarize_articles()
