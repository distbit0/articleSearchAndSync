import os
import sys
import json
import sqlite3
import hashlib
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set, Optional
from loguru import logger
from dotenv import load_dotenv
from openai import OpenAI
import concurrent.futures
import glob

# Import utils properly based on how it's structured in the project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import utils
from src.utils import getConfig
from src.textExtraction import extract_text_from_file, calculate_file_hash

# Constants
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
DB_FILENAME = "article_summaries.db"


def load_environment_variables() -> None:
    """Load environment variables from .env file."""
    potential_env_paths = [
        os.path.join(PROJECT_ROOT, ".env"),
        os.path.join(os.getcwd(), ".env"),
        os.path.abspath(".env"),
    ]

    for env_path in potential_env_paths:
        if os.path.exists(env_path):
            load_dotenv(dotenv_path=env_path)
            print(f"Loaded environment from: {env_path}")
            break


def setup_tag_database() -> str:
    """Setup the SQLite database for article tags if it doesn't exist.

    Returns:
        str: Path to the database file
    """
    os.makedirs(STORAGE_DIR, exist_ok=True)
    db_path = os.path.join(STORAGE_DIR, DB_FILENAME)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tags table if it doesn't exist
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            use_summary BOOLEAN,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Create article_tags table for many-to-many relationship with matches column
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS article_tags (
            article_id INTEGER,
            tag_id INTEGER,
            matches BOOLEAN NOT NULL DEFAULT 1,
            PRIMARY KEY (article_id, tag_id),
            FOREIGN KEY (article_id) REFERENCES article_summaries(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
        """
    )

    # Create tag_hash table to store hashes of tag properties
    # Used to determine if a tag's properties have changed
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tag_hashes (
            tag_id INTEGER PRIMARY KEY,
            property_hash TEXT,
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
        """
    )

    conn.commit()
    conn.close()
    return db_path


def get_tag_property_hash(description: str, use_summary: bool) -> str:
    """Calculate a hash of tag properties to detect changes.

    Args:
        description: The natural language description of the tag
        use_summary: Whether to use the article summary for evaluation

    Returns:
        str: Hash of the tag properties
    """
    # Create a string combining all properties that should trigger re-evaluation
    property_string = f"{description}|{use_summary}"
    return hashlib.md5(property_string.encode()).hexdigest()


class TagManager:
    """Class to handle database operations for article tags."""

    def __init__(self, db_path: str):
        """Initialize the TagManager with the database path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path

    def _get_connection(self) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
        """Get a database connection and cursor.

        Returns:
            Tuple[sqlite3.Connection, sqlite3.Cursor]: Database connection and cursor
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        return conn, cursor

    def sync_tags_from_config(self) -> None:
        """Synchronize tags from config.json to the database."""
        config = getConfig()
        tag_config = config.get("article_tags", {})

        if not tag_config:
            print("No tags found in config.json. Please add an 'article_tags' section.")
            return

        conn, cursor = self._get_connection()

        # Get existing tags from database
        cursor.execute("SELECT id, name, description, use_summary FROM tags")
        existing_tags = {
            row[1]: {"id": row[0], "description": row[2], "use_summary": bool(row[3])}
            for row in cursor.fetchall()
        }

        # Get property hashes for existing tags
        cursor.execute("SELECT tag_id, property_hash FROM tag_hashes")
        property_hashes = {row[0]: row[1] for row in cursor.fetchall()}

        # Track which tags from config were processed
        processed_tags = set()

        # Process tags from config
        for tag_name, tag_data in tag_config.items():
            processed_tags.add(tag_name)
            description = tag_data.get("description", "")
            use_summary = tag_data.get("use_summary", True)
            # Check if tag is enabled, default to True if not specified
            enabled = tag_data.get("enabled", True)

            # Calculate property hash
            new_hash = get_tag_property_hash(description, use_summary)

            if tag_name in existing_tags:
                # Tag exists, check if properties changed
                tag_id = existing_tags[tag_name]["id"]
                current_hash = property_hashes.get(tag_id)

                if current_hash != new_hash:
                    # Properties changed, update tag and mark for re-evaluation
                    cursor.execute(
                        "UPDATE tags SET description = ?, use_summary = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                        (description, use_summary, tag_id),
                    )

                    # Update property hash
                    if current_hash:
                        cursor.execute(
                            "UPDATE tag_hashes SET property_hash = ? WHERE tag_id = ?",
                            (new_hash, tag_id),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO tag_hashes (tag_id, property_hash) VALUES (?, ?)",
                            (tag_id, new_hash),
                        )

                    # Remove tag associations to force re-evaluation
                    cursor.execute(
                        "DELETE FROM article_tags WHERE tag_id = ?", (tag_id,)
                    )
                    print(f"Updated tag '{tag_name}' and cleared previous assignments")
            else:
                # New tag, add to database
                cursor.execute(
                    "INSERT INTO tags (name, description, use_summary) VALUES (?, ?, ?)",
                    (tag_name, description, use_summary),
                )
                tag_id = cursor.lastrowid

                # Add property hash
                cursor.execute(
                    "INSERT INTO tag_hashes (tag_id, property_hash) VALUES (?, ?)",
                    (tag_id, new_hash),
                )
                print(f"Added new tag '{tag_name}'")

        # Important: We no longer remove tags from the database when they're removed from config
        # We'll handle disabled/removed tags during the evaluation process

        conn.commit()
        conn.close()

    def create_folder_tags(self, articles_path: str) -> None:
        """Create tags based on folder structure.

        Also tracks when articles are moved between folders by:
        - Removing folder_X tags when an article is no longer in folder X
        - Adding prev_folder_X tags to indicate the article was previously in folder X

        Args:
            articles_path: Path to the articles directory
        """
        config = getConfig()
        folder_exclusions = config.get("foldersToExcludeFromCategorisation", [])

        conn, cursor = self._get_connection()

        # Get all articles from the database
        cursor.execute("SELECT id, file_name FROM article_summaries")
        articles = cursor.fetchall()

        # Get existing folder tags and prev_folder tags
        cursor.execute(
            "SELECT id, name FROM tags WHERE name LIKE 'folder_%' OR name LIKE 'prev_folder_%'"
        )
        tag_rows = cursor.fetchall()
        folder_tags = {
            row[1]: row[0] for row in tag_rows if row[1].startswith("folder_")
        }
        prev_folder_tags = {
            row[1]: row[0] for row in tag_rows if row[1].startswith("prev_folder_")
        }

        for article_id, file_name in articles:
            # Get current folder tags for this article
            cursor.execute(
                "SELECT t.name, at.tag_id FROM article_tags at "
                "JOIN tags t ON at.tag_id = t.id "
                "WHERE at.article_id = ? AND t.name LIKE 'folder_%'",
                (article_id,),
            )
            current_folder_tags = {row[0]: row[1] for row in cursor.fetchall()}

            # Find the article path using glob instead of getArticlePathsForQuery
            searchString = os.path.join(articles_path, "**", file_name)
            file_paths = glob.glob(searchString, recursive=True)

            # Track which folder tags should be kept
            should_keep_tags = set()

            for file_path in file_paths:
                if os.path.isabs(file_path) and os.path.isabs(articles_path):
                    rel_path = os.path.relpath(file_path, articles_path)
                    # Extract folders from path
                    folders = Path(rel_path).parent.parts

                    # Create folder tags for each subfolder
                    for folder in folders:
                        # Skip excluded folders and empty folder names
                        if folder in folder_exclusions or not folder:
                            continue

                        tag_name = f"folder_{folder}"
                        should_keep_tags.add(tag_name)

                        # Create folder tag if it doesn't exist
                        if tag_name not in folder_tags:
                            cursor.execute(
                                "INSERT INTO tags (name, description, use_summary) VALUES (?, ?, ?)",
                                (
                                    tag_name,
                                    f"Articles located in the '{folder}' folder",
                                    False,
                                ),
                            )
                            tag_id = cursor.lastrowid
                            folder_tags[tag_name] = tag_id
                            print(f"Created folder tag '{tag_name}'")
                        else:
                            tag_id = folder_tags[tag_name]

                        # Associate article with folder tag
                        try:
                            cursor.execute(
                                "INSERT INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, 1)",
                                (article_id, tag_id),
                            )
                        except sqlite3.IntegrityError:
                            # Tag already associated with article
                            pass

            # Handle removed folders
            for tag_name, tag_id in current_folder_tags.items():
                if tag_name not in should_keep_tags:
                    # Article is no longer in this folder, remove folder tag
                    folder_name = tag_name[7:]  # Remove 'folder_' prefix
                    prev_tag_name = f"prev_folder_{folder_name}"

                    # Remove the folder tag
                    cursor.execute(
                        "DELETE FROM article_tags WHERE article_id = ? AND tag_id = ?",
                        (article_id, tag_id),
                    )
                    print(f"Removed folder tag '{tag_name}' from article {article_id}")

                    # Create prev_folder tag if it doesn't exist
                    if prev_tag_name not in prev_folder_tags:
                        cursor.execute(
                            "INSERT INTO tags (name, description, use_summary) VALUES (?, ?, ?)",
                            (
                                prev_tag_name,
                                f"Articles previously located in the '{folder_name}' folder",
                                False,
                            ),
                        )
                        prev_tag_id = cursor.lastrowid
                        prev_folder_tags[prev_tag_name] = prev_tag_id
                        print(f"Created previous folder tag '{prev_tag_name}'")
                    else:
                        prev_tag_id = prev_folder_tags[prev_tag_name]

                    # Add the prev_folder tag to the article
                    try:
                        cursor.execute(
                            "INSERT INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, 1)",
                            (article_id, prev_tag_id),
                        )
                        print(
                            f"Added previous folder tag '{prev_tag_name}' to article {article_id}"
                        )
                    except sqlite3.IntegrityError:
                        # Tag already associated with article
                        pass

        conn.commit()
        conn.close()


class TagEvaluator:
    """Class for evaluating whether articles match tags."""

    def __init__(self):
        """Initialize the TagEvaluator."""
        self.config = getConfig()
        self.model = self.config.get("ai_model", "google/gemini-2.0-flash-001")
        self.batch_size = int(
            self.config.get("tag_batch_size", 3)
        )  # Default to 3 tags per batch

        # Load API key
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY not found in environment variables")
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")

        # Get optional referer info from environment variables
        self.referer = os.getenv("OPENROUTER_REFERER", "articleSearchAndSync")
        self.title = os.getenv("OPENROUTER_TITLE", "Article Search and Sync")

    def _create_openai_client(self) -> OpenAI:
        """Create and return an OpenAI client configured for OpenRouter.

        Returns:
            OpenAI: Configured OpenAI client
        """
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": self.referer,
                "X-Title": self.title,
            },
        )

    def evaluate_tags(
        self, text: str, tags_to_evaluate: List[Tuple[int, str, str]]
    ) -> Dict[int, bool]:
        """Evaluate if an article matches multiple tags using OpenRouter API.

        Args:
            text: Article text or summary to evaluate
            tags_to_evaluate: List of tuples containing (tag_id, tag_name, tag_description)

        Returns:
            Dict[int, bool]: Dictionary mapping tag_id to boolean (True if matched, False otherwise)
        """
        if not text or len(text.strip()) == 0:
            logger.warning("No text to evaluate for tags")
            return {tag_id: False for tag_id, _, _ in tags_to_evaluate}

        if not tags_to_evaluate:
            return {}

        try:
            client = self._create_openai_client()

            # Format the tag data for the prompt
            tag_info = []
            for i, (_, tag_name, tag_description) in enumerate(tags_to_evaluate):
                tag_info.append(
                    f"Tag {i+1}:\n- Name: {tag_name}\n- Description: {tag_description}"
                )

            tag_info_str = "\n\n".join(tag_info)
            tag_names = [tag_name for _, tag_name, _ in tags_to_evaluate]

            logger.info(
                f"Evaluating article for tags: {', '.join(tag_names)} using model: {self.model}"
            )

            system_prompt = """You are a helpful system that evaluates whether a text matches given tag descriptions. 
Your task is to determine if the article text is related to each of the provided tag descriptions.
You MUST respond in valid JSON format only."""

            user_prompt = f"""Please analyze the following text to determine if it matches each of the tag descriptions provided below. 
Respond in JSON format with the tag name as key and boolean true/false as value.

Tags to evaluate:

{tag_info_str}

Text to evaluate:
{text[:6000]}  # Limit text length to avoid token limits

Based on the tag descriptions, determine if this text matches each tag.
Your response must be valid JSON in this exact format:
{{
  "{tag_names[0]}": true or false,
  "{tag_names[1] if len(tag_names) > 1 else 'tag2'}": true or false,
  "{tag_names[2] if len(tag_names) > 2 else 'tag3'}": true or false
}}
Note: Only include actual tags in your response (do not include placeholder 'tag2' or 'tag3' if they weren't in the input).
"""

            response = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": self.referer,
                    "X-Title": self.title,
                },
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )

            # Extract the response and parse JSON
            result_text = response.choices[0].message.content.strip()

            # Retry logic for JSON parsing
            max_retries = 3
            retry_count = 0

            while retry_count < max_retries:
                try:
                    result_json = json.loads(result_text)

                    # Map the results back to tag_ids
                    results = {}
                    for tag_id, tag_name, _ in tags_to_evaluate:
                        if tag_name in result_json:
                            results[tag_id] = result_json[tag_name]
                        else:
                            logger.warning(
                                f"Tag '{tag_name}' not found in API response"
                            )
                            results[tag_id] = False

                    logger.info(f"Tag evaluation results: {result_json}")
                    return results

                except json.JSONDecodeError as e:
                    retry_count += 1
                    logger.warning(
                        f"Attempt {retry_count}: Failed to parse JSON response: {result_text}"
                    )

                    if retry_count >= max_retries:
                        logger.error(
                            f"All {max_retries} attempts failed to parse JSON response. Last error: {str(e)}"
                        )
                        return {tag_id: False for tag_id, _, _ in tags_to_evaluate}

                    # Modify the original user prompt with error information for retry
                    retry_user_prompt = f"""The previous response couldn't be parsed as valid JSON. The error was: {str(e)}

{user_prompt}

IMPORTANT: YOU MUST RETURN ONLY VALID JSON. No explanations or additional text."""

                    # Reuse the original request with slightly modified prompt
                    try:
                        retry_response = client.chat.completions.create(
                            extra_headers={
                                "HTTP-Referer": self.referer,
                                "X-Title": self.title,
                            },
                            model=self.model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": retry_user_prompt},
                            ],
                            response_format={"type": "json_object"},
                        )
                        result_text = retry_response.choices[0].message.content.strip()
                    except Exception as retry_error:
                        logger.error(f"Error during retry: {str(retry_error)}")
                        retry_count = max_retries  # Force exit from retry loop

        except Exception as e:
            error_message = f"Error evaluating tags: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"{error_message}\n{error_traceback}")
            print(error_message)
            traceback.print_exc()
            return {tag_id: False for tag_id, _, _ in tags_to_evaluate}

    def batch_evaluate_tags(
        self,
        article_id: int,
        file_name: str,
        text: str,
        tags_list: List[Tuple[int, str, str]],
    ) -> Dict[int, bool]:
        """Process a list of tags in batches to minimize API calls.

        Args:
            article_id: ID of the article
            file_name: Name of the article file (for logging)
            text: Text to evaluate (summary or full text)
            tags_list: List of tags to evaluate

        Returns:
            Dict[int, bool]: Dictionary mapping tag_id to boolean (True if matched, False otherwise)
        """
        if not tags_list or not text:
            return {}

        # Split tags into batches of size batch_size
        tag_batches = []
        for i in range(0, len(tags_list), self.batch_size):
            tag_batches.append(tags_list[i : i + self.batch_size])

        print(
            f"  Processing {len(tags_list)} tags in {len(tag_batches)} batches (batch size: {self.batch_size})"
        )

        # Process each batch of tags
        tag_results = {}
        for i, batch in enumerate(tag_batches):
            try:
                batch_tag_names = [tag_name for _, tag_name, _ in batch]
                print(
                    f"  Batch {i+1}/{len(tag_batches)}: Evaluating tags {', '.join(batch_tag_names)}"
                )

                # Evaluate tags in this batch
                batch_results = self.evaluate_tags(text, batch)
                tag_results.update(batch_results)

                print(
                    f"  Batch {i+1}/{len(tag_batches)}: Completed evaluation of {len(batch)} tags"
                )
            except Exception as e:
                error_message = f"Error processing batch {i+1}: {str(e)}"
                logger.error(error_message)
                print(error_message)
                # Continue with the next batch instead of failing the entire process

        return tag_results


class ArticleTagger:
    """Class to manage the process of applying tags to articles."""

    def __init__(self, db_path: str):
        """Initialize the ArticleTagger.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.config = getConfig()
        self.articles_path = self.config.get("articleFileFolder", "")
        self.max_articles_per_session = int(
            self.config.get("maxArticlesToTagPerSession", 100)
        )
        self.max_workers = int(self.config.get("llm_api_batch_size", 4))
        self.tag_evaluator = TagEvaluator()

    def _get_active_tag_ids(self) -> Set[int]:
        """Get IDs of all active tags from config.

        Returns:
            Set[int]: Set of active tag IDs
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all active tags from config (enabled or not explicitly disabled)
        active_tags = {}
        for tag_name, tag_data in self.config.get("article_tags", {}).items():
            # Skip tags marked as disabled
            if not tag_data.get("enabled", True):
                print(f"Skipping disabled tag '{tag_name}'")
                continue
            active_tags[tag_name] = tag_data

        # Get all tags from database
        cursor.execute("SELECT id, name, description, use_summary FROM tags")
        all_tags = cursor.fetchall()

        # Filter tags that are in the active_tags list
        active_tag_ids = []
        for tag_id, tag_name, _, _ in all_tags:
            if tag_name in active_tags or tag_name.startswith("folder_"):
                active_tag_ids.append(tag_id)

        conn.close()

        # Convert to set for faster lookups
        return set(active_tag_ids)

    def _get_articles_needing_tagging(self) -> List[Tuple[int, str, str, str]]:
        """Get all articles that need tagging.

        Returns:
            List[Tuple[int, str, str, str]]: List of articles (id, file_hash, file_name, summary)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all articles that need tagging
        cursor.execute(
            """
            SELECT a.id, a.file_hash, a.file_name, a.summary 
            FROM article_summaries a
            WHERE EXISTS (
                SELECT 1 FROM tags t
                WHERE t.id NOT IN (
                    SELECT tag_id FROM article_tags WHERE article_id = a.id
                )
            )
            """
        )
        articles = cursor.fetchall()

        conn.close()

        return articles

    def _get_tags_for_article(
        self, article_id: int, active_tag_ids: Set[int]
    ) -> List[Tuple[int, str, str, bool]]:
        """Get tags that need to be evaluated for an article.

        Args:
            article_id: ID of the article
            active_tag_ids: Set of active tag IDs

        Returns:
            List[Tuple[int, str, str, bool]]: List of tags (id, name, description, use_summary)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get tags that need to be evaluated for this article
        cursor.execute(
            """
            SELECT t.id, t.name, t.description, t.use_summary 
            FROM tags t
            WHERE t.id NOT IN (
                SELECT tag_id FROM article_tags WHERE article_id = ?
            )
            """,
            (article_id,),
        )
        tags_to_evaluate = cursor.fetchall()

        conn.close()

        # Filter out folder tags and inactive tags
        return [
            (tag_id, tag_name, tag_description, use_summary)
            for tag_id, tag_name, tag_description, use_summary in tags_to_evaluate
            if not tag_name.startswith("folder_") and tag_id in active_tag_ids
        ]

    def _apply_tag_results(self, article_id: int, tag_results: Dict[int, bool]) -> int:
        """Apply tag results to the database.

        Args:
            article_id: ID of the article
            tag_results: Dictionary mapping tag_id to boolean (True if matched)

        Returns:
            int: Number of tags applied
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        tags_applied = 0
        matching_tags = 0
        for tag_id, matched in tag_results.items():
            try:
                cursor.execute(
                    "INSERT INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, ?)",
                    (article_id, tag_id, matched),
                )

                # Get tag name for logging
                cursor.execute("SELECT name FROM tags WHERE id = ?", (tag_id,))
                tag_name_result = cursor.fetchone()
                tag_name = tag_name_result[0] if tag_name_result else f"ID:{tag_id}"

                if matched:
                    print(f"  Applied tag '{tag_name}' to article")
                    matching_tags += 1
                else:
                    print(f"  Recorded non-match for tag '{tag_name}'")

                tags_applied += 1
            except sqlite3.IntegrityError:
                # Tag already applied or recorded as non-match, update it
                cursor.execute(
                    "UPDATE article_tags SET matches = ? WHERE article_id = ? AND tag_id = ?",
                    (matched, article_id, tag_id),
                )

                # Get tag name for logging
                cursor.execute("SELECT name FROM tags WHERE id = ?", (tag_id,))
                tag_name_result = cursor.fetchone()
                tag_name = tag_name_result[0] if tag_name_result else f"ID:{tag_id}"

                if matched:
                    print(f"  Updated tag '{tag_name}' to match article")
                    matching_tags += 1
                else:
                    print(f"  Updated tag '{tag_name}' to non-match")

        conn.commit()
        conn.close()

        return matching_tags

    def _process_tags_with_executor(
        self,
        article_id: int,
        file_name: str,
        text: str,
        tags_list: List[Tuple[int, str, str]],
    ) -> Dict[int, bool]:
        """Process a list of tags using ThreadPoolExecutor.

        Args:
            article_id: ID of the article
            file_name: Name of the article file
            text: Text to evaluate (summary or full text)
            tags_list: List of tags to evaluate

        Returns:
            Dict[int, bool]: Dictionary mapping tag_id to boolean (True if matched)
        """
        if not tags_list or not text:
            return {}

        # Reorganize tags into balanced batches for parallel processing
        tag_batches = []
        batch_count = min(
            self.max_workers,
            max(
                1,
                len(tags_list) // self.tag_evaluator.batch_size
                + (1 if len(tags_list) % self.tag_evaluator.batch_size > 0 else 0),
            ),
        )

        # Create roughly equal-sized batches based on the number of workers
        for i in range(batch_count):
            start_idx = i * len(tags_list) // batch_count
            end_idx = (i + 1) * len(tags_list) // batch_count
            if end_idx > start_idx:  # Ensure we don't create empty batches
                tag_batches.append(tags_list[start_idx:end_idx])

        print(
            f"  Processing {len(tags_list)} tags with {len(tag_batches)} parallel workers"
        )

        tag_results = {}
        tags_processed = 0

        # Use ThreadPoolExecutor to process batches in parallel
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(tag_batches)
        ) as executor:
            # Submit batch processing tasks
            future_to_batch = {
                executor.submit(
                    self.tag_evaluator.batch_evaluate_tags,
                    article_id,
                    file_name,
                    text,
                    batch,
                ): batch
                for batch in tag_batches
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_batch):
                batch = future_to_batch[future]
                batch_tag_names = [tag_name for _, tag_name, _ in batch]

                try:
                    batch_results = future.result()
                    tags_processed += len(batch)
                    tag_results.update(batch_results)

                    print(
                        f"  [{tags_processed}/{len(tags_list)}] Processed batch with tags: {', '.join(batch_tag_names)}"
                    )
                except Exception as e:
                    tags_processed += len(batch)
                    print(
                        f"  [{tags_processed}/{len(tags_list)}] Error processing batch: {str(e)}"
                    )

        return tag_results

    def apply_tags_to_articles(self) -> None:
        """Apply tags to all articles in the database."""
        # Get active tag IDs
        active_tag_ids = self._get_active_tag_ids()

        # Get articles needing tagging
        articles = self._get_articles_needing_tagging()

        # Limit the number of articles to process
        if len(articles) > self.max_articles_per_session:
            print(
                f"Limiting to {self.max_articles_per_session} articles due to maxArticlesToTagPerSession config setting"
            )
            logger.info(
                f"Limiting to {self.max_articles_per_session} articles due to maxArticlesToTagPerSession config setting"
            )
            articles = articles[: self.max_articles_per_session]

        print(f"Found {len(articles)} articles that need tagging")

        # Process each article
        for article_id, file_hash, file_name, summary in articles:

            # Get tags that need to be evaluated for this article
            tags_to_evaluate = self._get_tags_for_article(article_id, active_tag_ids)

            if not tags_to_evaluate:
                # print(f"  No tags to evaluate for this article")
                continue
            print(f"Tagging article: {file_name}")

            # Find the article path
            file_paths = glob.glob(
                os.path.join(self.articles_path, "**", file_name), recursive=True
            )
            if not file_paths:
                print(f"  Could not find article file: {file_name}")
                continue

            file_path = file_paths[0]
            # Group tags by whether they use summary or full text
            tags_using_summary = [
                (tag_id, tag_name, tag_description)
                for tag_id, tag_name, tag_description, use_summary in tags_to_evaluate
                if use_summary
            ]

            tags_using_fulltext = [
                (tag_id, tag_name, tag_description)
                for tag_id, tag_name, tag_description, use_summary in tags_to_evaluate
                if not use_summary
            ]

            # Extract article text for full-text evaluations
            article_text = None
            if tags_using_fulltext:
                try:
                    article_text, _, _ = extract_text_from_file(file_path)
                    if not article_text or len(article_text.strip()) == 0:
                        print(f"  Warning: Extracted text from {file_name} is empty")
                        article_text = None
                except Exception as e:
                    print(f"  Error extracting text from {file_name}: {str(e)}")
                    article_text = None

                # Skip full-text evaluation if text extraction failed
                if article_text is None and tags_using_fulltext:
                    print(
                        f"  Skipping {len(tags_using_fulltext)} full-text tags due to text extraction failure"
                    )
                    tags_using_fulltext = []

            # Initialize tag results
            tag_results = {}

            # Process summary-based tags
            if tags_using_summary and summary:
                summary_results = self._process_tags_with_executor(
                    article_id, file_name, summary, tags_using_summary
                )
                tag_results.update(summary_results)

            # Process full-text tags
            if tags_using_fulltext and article_text:
                fulltext_results = self._process_tags_with_executor(
                    article_id, file_name, article_text, tags_using_fulltext
                )
                tag_results.update(fulltext_results)

            # Apply tags based on results
            matching_tags = self._apply_tag_results(article_id, tag_results)
            total_tags = len(tag_results)

            if matching_tags == 0:
                print(
                    f"  No matching tags found for this article (evaluated {total_tags} tags)"
                )
            else:
                print(
                    f"  Successfully applied {matching_tags} matching tags to article (evaluated {total_tags} tags)"
                )


def main():
    """Main function to run the tagging process."""
    # Load environment variables
    load_environment_variables()

    # Setup database
    db_path = setup_tag_database()

    # Create manager instances
    tag_manager = TagManager(db_path)
    article_tagger = ArticleTagger(db_path)

    # Sync tags from config
    print("Syncing tags from config...")
    tag_manager.sync_tags_from_config()

    # Get configuration
    config = getConfig()
    articles_path = config.get("articleFileFolder", "")

    if not articles_path:
        print("No articles directory specified in config")
        return

    # Create folder tags
    print("\nCreating folder tags...")
    tag_manager.create_folder_tags(articles_path)

    # Apply tags to articles
    print("\nApplying tags to articles...")
    article_tagger.apply_tags_to_articles()

    print("\nTagging process completed")


if __name__ == "__main__":
    main()
