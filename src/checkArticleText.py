#!/usr/bin/env python3
import os
import sys
import json
import traceback
import time
from typing import Optional, Dict, Any, List, Tuple
import concurrent.futures
import re
from dotenv import load_dotenv
from openai import OpenAI
import requests
import timeout_decorator

# Import functions from textExtraction.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import utils
from src.utils import getConfig
from src.textExtraction import (
    extract_text_from_file,
    TextExtractionError,
    calculate_file_hash,
)

# Load environment variables from the correct path
potential_env_paths = [
    os.path.join(os.getcwd(), ".env"),
]

for env_path in potential_env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}")
        break
else:
    print("Warning: No .env file found.")

# Get project root directory
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# File to store incomprehensible files
INCOMPREHENSIBLE_FILE = os.path.join(project_root, "artifacts_report.txt")
# File to store list of problematic articles
PROBLEM_ARTICLES_FILE = os.path.join(project_root, "problem_articles.txt")
# File to store files that couldn't be properly read
UNREADABLE_FILES_LOG = os.path.join(project_root, "unreadable_files.log")

# API request timeout in seconds
API_TIMEOUT = 30


def check_article_for_comprehension(file_path: str) -> Tuple[bool, str, str]:
    """Check an article for text quality issues that make it incomprehensible.

    Args:
        file_path: Path to the article file

    Returns:
        Tuple[bool, str, str]:
            - Whether text is incomprehensible
            - Extracted text
            - Message with details
    """
    try:
        file_name = os.path.basename(file_path)
        print(f"\nChecking: {file_name}")

        # Extract text from the file
        config = getConfig()
        max_words = int(config.get("summary_in_max_words", 3000))

        text, extraction_method, word_count = extract_text_from_file(
            file_path, max_words
        )

        # Limit to first 1000 words for quality checking (to save tokens)
        words = text.split()
        check_text = " ".join(words[:1000]) if len(words) > 1000 else text

        # Check for comprehension issues using the LLM
        try:
            result = check_text_with_llm(check_text)

            # Extract the result
            is_incomprehensible = result["incomprehensible"]
            explanation = result.get("explanation", "No explanation provided")

            if is_incomprehensible:
                message = f"Text quality issue: {explanation}"
                return True, text, message
            else:
                return False, text, "No comprehension issues detected"
        except Exception as e:
            error_message = f"LLM check failed: {str(e)}"
            print(error_message)
            return False, text, error_message

    except TextExtractionError as e:
        error_message = f"Failed to extract text: {str(e)}"
        print(error_message)
        # Log the unreadable file with the error message
        log_unreadable_file(file_path, error_message)
        return False, "", error_message
    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
        error_traceback = traceback.format_exc()
        traceback.print_exc()
        # Log the unreadable file with detailed error information
        log_unreadable_file(file_path, error_message, error_traceback)
        return False, "", error_message


@timeout_decorator.timeout(API_TIMEOUT, use_signals=False)
def check_text_with_llm(text: str) -> Dict[str, Any]:
    """Check text quality issues using OpenRouter API.

    Args:
        text: Text to check

    Returns:
        Dict containing:
            - incomprehensible: Whether the text is incomprehensible
            - explanation: Explanation from the LLM
    """
    if not text or len(text.strip()) == 0:
        return {"incomprehensible": False, "explanation": "No text to check"}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    # Get configuration from config.json
    config = getConfig()
    model = config.get("ai_model", "openai/o3-mini")

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
            timeout=API_TIMEOUT,
        )

        print(f"Sending text quality check request to OpenRouter with model: {model}")

        # Set a reasonable max_tokens
        max_tokens = 500

        system_prompt = "You are a system that identifies whether an article has so many text quality issues that you aren't able to understand its meaning"
        user_prompt = f"""Please analyze the following text extracted from a document and determine if it contains text quality issues which are so bad as to make it incomprehensible to you and which would prevent you from being able to write a meaningful summary of the text

{{
    "incomprehensible": true/false,
    "explanation": "Brief explanation of why it is incomprehensible"
}}

Text to analyze:
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
            response_format={"type": "json_object"},
        )

        # Extract and parse the response
        result_text = response.choices[0].message.content

        try:
            # Extract JSON from the response if enclosed in markdown code blocks
            if "```json" in result_text and "```" in result_text:
                json_match = re.search(r"```json\s*(.*?)\s*```", result_text, re.DOTALL)
                if json_match:
                    result_text = json_match.group(1)

            # Parse the JSON response
            result = json.loads(result_text)

            # Convert old format if needed (for backwards compatibility)
            if "summarisable" in result and "incomprehensible" not in result:
                result["incomprehensible"] = not result["summarisable"]
                del result["summarisable"]

            # Ensure the expected fields are present
            if "incomprehensible" not in result:
                result["incomprehensible"] = False
            if "explanation" not in result:
                result["explanation"] = "No explanation provided."

            print(f"Text quality check result: {result['incomprehensible']}")
            if result["incomprehensible"]:
                print(f"Explanation: {result['explanation']}")

            return result
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            print(f"Response text: {result_text}")
            return {
                "incomprehensible": False,
                "explanation": f"Failed to parse LLM response: {str(e)}",
            }

    except timeout_decorator.TimeoutError:
        print("API request timed out")
        raise
    except Exception as e:
        print(f"Error in LLM check: {str(e)}")
        traceback.print_exc()
        raise


def save_incomprehensible_report(file_path: str, text_sample: str, explanation: str):
    """Save details of incomprehensible articles to a report file.

    Args:
        file_path: Path to the article file
        text_sample: Sample of the text with quality issues
        explanation: Explanation of the issues found
    """
    with open(INCOMPREHENSIBLE_FILE, "a") as report:
        report.write(f"FILE: {file_path}\n")
        report.write(f"EXPLANATION: {explanation}\n")
        report.write(f"TEXT SAMPLE:\n{'-'*80}\n")
        # Limit sample to first 4000 characters
        sample = text_sample[:4000] + "..." if len(text_sample) > 4000 else text_sample
        report.write(f"{sample}\n")
        report.write(f"{'-'*80}\n\n")

    # Also add to the simple list file
    with open(PROBLEM_ARTICLES_FILE, "a") as problem_list:
        problem_list.write(f"{file_path}|{explanation.replace('|', ' ')}\n")


def log_unreadable_file(
    file_path: str, error_message: str, error_traceback: str = None
):
    """Log files that couldn't be properly read to a separate log file.

    Args:
        file_path: Path to the article file
        error_message: Error message explaining why the file couldn't be read
        error_traceback: Optional traceback for detailed error information
    """
    with open(UNREADABLE_FILES_LOG, "a") as log_file:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"[{timestamp}] FILE: {file_path}\n")
        log_file.write(f"ERROR: {error_message}\n")

        if error_traceback:
            log_file.write(f"TRACEBACK:\n{'-'*80}\n")
            log_file.write(f"{error_traceback}\n")

        log_file.write(f"{'-'*80}\n\n")


def check_all_articles(start_index: int = 0) -> None:
    """Check all articles for text quality issues and report issues.

    Args:
        start_index: Index to start from (useful for resuming interrupted runs)
    """
    config = getConfig()
    articles_path = config.get("articleFileFolder", "/home/pimania/ebooks/")

    # Get supported formats from the config
    supported_formats = config.get("docFormatsToMove", [])

    # Get all articles with the supported formats
    print(
        f"Searching for articles in {articles_path} with formats: {supported_formats}"
    )

    article_dict = utils.getArticlePathsForQuery("*", supported_formats, articles_path)

    print(f"Found {len(article_dict)} articles to check")
    # Get maximum articles per session from config
    max_articles_per_session = int(config.get("maxSummariesPerSession", 100))

    # Respect the maxSummariesPerSession limit
    article_paths = list(article_dict.keys())
    if len(article_paths) > max_articles_per_session:
        print(
            f"Limiting to {max_articles_per_session} articles as per maxSummariesPerSession config"
        )
        article_paths = article_paths[:max_articles_per_session]

    # Apply the start index (for resuming interrupted runs)
    if start_index > 0 and start_index < len(article_paths):
        print(
            f"Starting from index {start_index} ({len(article_paths) - start_index} articles remaining)"
        )
        article_paths = article_paths[start_index:]

    # Initialize or clear the incomprehensible report file
    with open(INCOMPREHENSIBLE_FILE, "w") as report:
        report.write(
            f"MAJOR TEXT QUALITY ISSUES REPORT - {len(article_paths)} articles checked\n"
        )
        report.write(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.write(
            "Note: This report only includes articles with SEVERE text quality issues that would impair comprehension.\n\n"
        )

    # Initialize or clear the problem articles list file
    with open(PROBLEM_ARTICLES_FILE, "w") as problem_list:
        problem_list.write("# List of articles with major text quality issues\n")
        problem_list.write("# Format: file_path|explanation\n\n")

    # Initialize or clear the unreadable files log
    with open(UNREADABLE_FILES_LOG, "w") as unreadable_log:
        unreadable_log.write(
            f"UNREADABLE FILES LOG - Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        unreadable_log.write(
            "This log contains files that couldn't be properly read with detailed error information\n\n"
        )

    # Count of problematic articles
    problematic_count = 0

    # Process articles sequentially
    for i, article_path in enumerate(article_paths):
        try:
            print(f"[{i+start_index+1}/{len(article_paths)}] ", end="")
            is_incomprehensible, text, message = check_article_for_comprehension(
                article_path
            )

            if is_incomprehensible:
                problematic_count += 1
                print(f" {os.path.basename(article_path)} - {message}")

                # Save to report file
                save_incomprehensible_report(article_path, text, message)
            else:
                print(f" {os.path.basename(article_path)} - No quality issues detected")

            # Save progress regularly
            if (i + 1) % 10 == 0:
                print(f"Progress: {i+1}/{len(article_paths)} articles checked")

        except KeyboardInterrupt:
            print("\nProcess interrupted by user. Saving current progress...")
            print(
                f"To resume, run: python src/checkArticleText.py --start-index {i+start_index}"
            )
            break
        except Exception as e:
            print(f"Error processing {os.path.basename(article_path)}: {e}")
            traceback.print_exc()

    # Write summary to the report file
    with open(INCOMPREHENSIBLE_FILE, "a") as report:
        report.write(f"\n\nSUMMARY\n{'='*80}\n")
        report.write(f"Total articles checked: {len(article_paths)}\n")
        report.write(f"Articles with text quality issues: {problematic_count}\n\n")

    print(
        f"\nArticle text quality check complete. Results saved to {INCOMPREHENSIBLE_FILE}"
    )
    print(
        f"Found {problematic_count} articles with text quality issues out of {len(article_paths)} checked"
    )
    print(f"List of problematic articles saved to {PROBLEM_ARTICLES_FILE}")
    print(f"Unreadable files log saved to {UNREADABLE_FILES_LOG}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Check for text quality issues in article files"
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Index to start from (useful for resuming interrupted runs)",
    )
    args = parser.parse_args()

    try:
        check_all_articles(args.start_index)
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
