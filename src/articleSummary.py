import random
import traceback
import sys
import os
from pathlib import Path
from typing import Optional, Tuple
import concurrent.futures
from loguru import logger
from dotenv import load_dotenv
from openai import OpenAI

from .utils import calculate_normal_hash, getConfig, getArticlePathsForQuery
from .textExtraction import extract_text_from_file, TextExtractionError
from . import db

# Configure loguru logger
log_file_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs",
    "summary.log",
)
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add(
    log_file_path,
    rotation="5 MB",
    retention=3,
    level="WARNING",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)

# Load environment variables from one of multiple potential .env locations
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
    return db.setup_database()


def summarize_with_openrouter(text: str) -> Tuple[str, bool]:
    """Generate a summary of the text using the OpenRouter API.

    Args:
        text: Text to summarize

    Returns:
        Tuple[str, bool]: Generated summary and flag indicating if the text was sufficient.
    """
    if not text or not text.strip():
        logger.warning("No text to summarize")
        return "No text to summarize", False

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not found in environment variables")
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    config = getConfig()
    model = config.get("ai_model")
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

        system_prompt = (
            "You are a helpful system that generates concise summaries of academic or educational content. "
            "You must first assess if the provided text contains sufficient content to generate a meaningful summary. "
            "If the text is too short, fragmented, or lacks substantive content, respond with "
            '"<summary>[INSUFFICIENT_TEXT]</summary>" at the beginning of your response. '
            "DO NOT respond with [INSUFFICIENT_TEXT] if there is substantive content but the text merely ends abruptly/not at the end of a sentence. "
            "ALWAYS return your summary enclosed within <summary></summary> tags. "
            "ONLY put the summary itself inside these tags, not any other part of your response."
        )

        user_prompt = (
            f"Please analyze the following text:\n\n{text}\n\n"
            "First, determine if the text provides enough substantial content to write a meaningful summary. "
            "If the text is too short, fragmented, or clearly not the full article (e.g., just metadata, table of contents, or a small snippet), "
            'respond with "<summary>[INSUFFICIENT_TEXT]</summary>" followed by a brief explanation of why the text is insufficient.\n\n'
            "If the text IS sufficient, please summarize it in a concise but informative way that captures the main arguments, principles, "
            'concepts, cruxes, intuitions, explanations and conclusions. Do not say things like "the author argues that..." or '
            '"the text explains how...".\n\n'
            "IMPORTANT: Return ONLY your summary enclosed within <summary></summary> tags. Do not include any other text outside these tags."
        )

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
        )

        full_response = response.choices[0].message.content
        import re

        summary_match = re.search(r"<summary>(.*?)</summary>", full_response, re.DOTALL)
        if summary_match:
            summary = summary_match.group(1).strip()
        else:
            error_message = "Summary tags not found in model response"
            logger.error(f"{error_message}. Response: {full_response}")
            return f"Failed to generate summary: {error_message}", False

        if summary.startswith("[INSUFFICIENT_TEXT]"):
            logger.debug(f"Insufficient text detected: {summary}")
            return summary, False

        return summary, True

    except Exception as e:
        error_message = f"Error generating summary: {str(e)}"
        logger.error(f"{error_message}\n{traceback.format_exc()}")
        traceback.print_exc()
        return f"Failed to generate summary: {error_message}", False


def get_article_summary(file_path: str) -> Tuple[str, bool]:
    """Get or create a summary for an article.

    Args:
        file_path: Path to the article file

    Returns:
        Tuple[str, bool]: Article summary and a flag indicating if text was sufficient.
    """
    file_hash = calculate_normal_hash(file_path)
    file_name = os.path.basename(file_path)
    file_format = os.path.splitext(file_path)[1].lower().lstrip(".")

    article = db.get_article_by_hash(file_hash)
    if article:
        summary = article["summary"]
        if summary is not None and summary != "":
            if summary == "failed_to_summarise":
                logger.debug(
                    f"Skipping file {file_name} due to previous insufficient text"
                )
                return summary, False
            elif summary == "failed_to_extract":
                logger.debug(
                    f"File {file_name} had extraction issues; attempting to summarize again"
                )
            else:
                return summary, True
        else:
            logger.debug(
                f"File {file_name} exists in DB but has not been summarized yet"
            )

    try:
        config = getConfig()
        max_words = int(config.get("summary_in_max_words", 3000))
        text, extraction_method, word_count = extract_text_from_file(
            file_path, max_words
        )
        summary, is_sufficient = summarize_with_openrouter(text)

        if not is_sufficient and "[INSUFFICIENT_TEXT]" in summary:
            db_summary = "failed_to_summarise"
            logger.warning(
                f"Insufficient text for file: {file_path}, marking as failed_to_summarise: {summary}"
            )
        else:
            db_summary = summary
            logger.debug(f"Successfully created summary for file: {file_path}")

        db.update_article_summary(
            file_hash, file_name, file_format, db_summary, extraction_method, word_count
        )
        return summary, is_sufficient

    except TextExtractionError as te:
        if not getattr(te, "already_logged", False):
            logger.error(f"Error extracting text from article: {str(te)}")
        db.add_file_to_database(file_hash, file_name, file_format)
        return "Temporary text extraction error", False

    except Exception as e:
        error_message = f"Error summarizing article: {str(e)}"
        logger.error(error_message)
        if os.environ.get("DEBUG", "false").lower() == "true":
            logger.debug(traceback.format_exc())
        return f"Temporary error: {error_message}", False


def summarize_articles(articles_path: Optional[str] = None, query: str = "*") -> None:
    """Summarize all articles in the given path that don't have summaries yet.

    Uses parallel processing to summarize multiple articles simultaneously.

    Args:
        articles_path: Path to the articles directory.
        query: Query string to filter articles (default: "*" for all articles).
    """
    if not articles_path:
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")
        if not articles_path:
            logger.error("No articles directory specified in config or argument")
            return

    if not os.path.isabs(articles_path):
        articles_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), articles_path
        )

    db.setup_database()
    articles_needing_summary = db.get_articles_needing_summary()
    logger.info(f"Found {len(articles_needing_summary)} articles needing summarization")

    if not articles_needing_summary:
        logger.info("No articles need summarization")
        return

    articles_to_summarize = []
    config = getConfig()
    max_summaries_per_session = int(config.get("maxSummariesPerSession", 150))
    random.shuffle(articles_needing_summary)

    for file_hash, file_name in articles_needing_summary:
        if len(articles_to_summarize) >= max_summaries_per_session:
            logger.info(
                f"Reached limit of {max_summaries_per_session} articles, stopping"
            )
            break
        file_path = os.path.join(articles_path, file_name)
        if file_path:
            articles_to_summarize.append(file_path)
        else:
            logger.warning(f"Could not find path for {file_name} in {articles_path}")

    logger.info(f"{len(articles_to_summarize)} articles need summarization")
    if not articles_to_summarize:
        logger.info("No articles to summarize")
        return

    max_workers = int(config.get("llm_api_batch_size", 4))
    total_articles = len(articles_to_summarize)
    successful = 0
    failed = 0
    insufficient = 0
    summary_word_counts = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_article = {
            executor.submit(process_single_article, path): path
            for path in articles_to_summarize
        }
        for future in concurrent.futures.as_completed(future_to_article):
            article_path = future_to_article[future]
            try:
                success, message, is_sufficient, summary = future.result()
                if success:
                    if is_sufficient:
                        logger.debug(
                            f"Successfully summarized: {article_path} - {message}"
                        )
                        successful += 1
                        word_count = len(summary.split())
                        if word_count:
                            summary_word_counts.append(word_count)
                    else:
                        insufficient += 1
                else:
                    logger.debug(f"Failed to summarize: {article_path} - {message}")
                    failed += 1
            except Exception as e:
                logger.error(
                    f"Failed to summarize: {article_path} - {str(e)}\n{traceback.format_exc()}"
                )
                failed += 1

    if summary_word_counts:
        avg_word_count = sum(summary_word_counts) / len(summary_word_counts)
        print(f"Average word count in generated summaries: {avg_word_count:.2f} words")
        logger.info(
            f"Average word count in generated summaries: {avg_word_count:.2f} words"
        )

    logger.info(
        f"Summary: Processed {total_articles} articles - {successful} successful, {insufficient} insufficient text, {failed} failed"
    )


def process_single_article(article_path: str) -> Tuple[bool, str, bool, str]:
    """Process a single article for summarization.

    Args:
        article_path: Path to the article file.

    Returns:
        Tuple[bool, str, bool, str]: Success status, message, sufficiency flag, and summary.
    """
    try:
        summary, is_sufficient = get_article_summary(article_path)
        if summary.startswith("Failed to summarize article:"):
            return False, summary, False, ""
        if not is_sufficient:
            return (
                True,
                f"Insufficient text detected ({len(summary)} chars)",
                False,
                summary,
            )
        return True, f"Summary generated ({len(summary)} chars)", True, summary
    except Exception as e:
        error_message = f"Error processing article: {str(e)}"
        logger.error(f"{error_message}\n{traceback.format_exc()}")
        return False, error_message, False, ""


def add_files_to_database(articles_path: Optional[str] = None) -> int:
    """Add all supported files to the database without summarizing.

    Args:
        articles_path: Path to the articles directory.

    Returns:
        int: Number of new files added to the database.
    """
    if not articles_path:
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")
        if not articles_path:
            logger.error("Article file folder not found in config")
            return 0

    logger.debug(f"Adding files to database from: {articles_path}")
    db.setup_database()
    config = getConfig()
    file_names_to_skip = config.get("fileNamesToSkip", [])
    existing_hashes = set(db.get_all_file_hashes())
    added_count = 0
    all_article_paths = getArticlePathsForQuery("*")
    logger.info(f"Found {len(all_article_paths)} files in {articles_path}.")

    for file_path in all_article_paths:
        file_name = os.path.basename(file_path)
        if file_name in file_names_to_skip:
            continue
        try:
            file_hash = calculate_normal_hash(file_path)
            if file_hash in existing_hashes:
                continue
            file_ext = os.path.splitext(file_name)[1].lstrip(".")
            db.add_file_to_database(file_hash, file_name, file_ext)
            existing_hashes.add(file_hash)
            added_count += 1
            if added_count % 100 == 0:
                logger.debug(f"Added {added_count} new files to database")
        except Exception as e:
            logger.error(f"Error adding file to database: {file_path}: {str(e)}")
            traceback.print_exc()

    logger.info(f"Added a total of {added_count} new files to database")
    return added_count


def remove_nonexistent_files_from_database(articles_path: Optional[str] = None) -> int:
    """Remove database entries for files that no longer exist on the filesystem.

    Args:
        articles_path: Path to the articles directory.

    Returns:
        int: Number of files removed from the database.
    """
    if not articles_path:
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")
        if not articles_path:
            logger.error("Article file folder not found in config")
            return 0

    logger.debug(f"Checking for nonexistent files in database from: {articles_path}")
    existing_files = {os.path.basename(path) for path in getArticlePathsForQuery("*")}
    removed_count = db.remove_nonexistent_files(existing_files)
    if removed_count > 0:
        logger.info(
            f"Removed {removed_count} entries for nonexistent files from database"
        )
    else:
        logger.info("No nonexistent files found in database")
    return removed_count


def remove_orphaned_tags_from_database() -> int:
    """Remove tags from the database that don't have any associated articles.

    Returns:
        int: Number of orphaned tags removed from the database.
    """
    logger.debug("Checking for orphaned tags in database")
    removed_count = db.remove_orphaned_tags()
    if removed_count > 0:
        logger.info(f"Removed {removed_count} orphaned tags from database")
    else:
        logger.info("No orphaned tags found in database")
    return removed_count
