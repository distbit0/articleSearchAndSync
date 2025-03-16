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

# Import utils properly based on how it's structured in the project
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import utils
from src.utils import getConfig, getArticlePathsForQuery
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

        Args:
            articles_path: Path to the articles directory
        """
        config = getConfig()
        folder_exclusions = config.get("foldersToExcludeFromCategorisation", [])

        conn, cursor = self._get_connection()

        # Get all articles from the database
        cursor.execute("SELECT id, file_name FROM article_summaries")
        articles = cursor.fetchall()

        # Get existing folder tags
        cursor.execute("SELECT id, name FROM tags WHERE name LIKE 'folder_%'")
        folder_tags = {row[1]: row[0] for row in cursor.fetchall()}

        for article_id, file_name in articles:
            # Find the article path from the file_name
            file_paths = getArticlePathsForQuery(
                "*", [], articles_path, fileName=file_name
            )

            for file_path in file_paths:
                if file_name in file_path:
                    # Get relative path to extract folders
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

        conn.commit()
        conn.close()


class TagEvaluator:
    """Class for evaluating whether articles match tags."""

    def __init__(self):
        """Initialize the TagEvaluator."""
        self.config = getConfig()
        self.model = self.config.get("ai_model", "google/gemini-2.0-flash-001")

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
            try:
                result_json = json.loads(result_text)

                # Map the results back to tag_ids
                results = {}
                for tag_id, tag_name, _ in tags_to_evaluate:
                    if tag_name in result_json:
                        results[tag_id] = result_json[tag_name]
                    else:
                        logger.warning(f"Tag '{tag_name}' not found in API response")
                        results[tag_id] = False

                logger.info(f"Tag evaluation results: {result_json}")
                return results

            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {result_text}")
                return {tag_id: False for tag_id, _, _ in tags_to_evaluate}

        except Exception as e:
            error_message = f"Error evaluating tags: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"{error_message}\n{error_traceback}")
            print(error_message)
            traceback.print_exc()
            return {tag_id: False for tag_id, _, _ in tags_to_evaluate}

    def evaluate_single_tag(
        self, text: str, tag_name: str, tag_description: str
    ) -> bool:
        """Evaluate if an article matches a tag using OpenRouter API.

        Note: This is a legacy function that uses the batch function internally.
        It's kept for backward compatibility.

        Args:
            text: Article text or summary to evaluate
            tag_name: Name of the tag
            tag_description: Description of the tag

        Returns:
            bool: True if the article matches the tag, False otherwise
        """
        tag_id = -1  # Temporary ID for single tag evaluation
        results = self.evaluate_tags(text, [(tag_id, tag_name, tag_description)])
        return results.get(tag_id, False)

    def process_single_tag(
        self, article_id: int, file_name: str, text: str, tag_data: Tuple[int, str, str]
    ) -> Tuple[bool, str, Dict[int, bool]]:
        """Process a single tag evaluation.

        Args:
            article_id: ID of the article being evaluated
            file_name: Name of the article file (for logging)
            text: Article text or summary to evaluate
            tag_data: Tuple containing (tag_id, tag_name, tag_description)

        Returns:
            Tuple[bool, str, Dict[int, bool]]: Success status, result message, and tag results dict
        """
        tag_id, tag_name, tag_description = tag_data
        try:
            # Evaluate single tag using the legacy function
            is_match = self.evaluate_single_tag(text, tag_name, tag_description)
            return (
                True,
                f"Successfully evaluated tag '{tag_name}' for article '{file_name}'",
                {tag_id: is_match},
            )
        except Exception as e:
            error_message = f"Error evaluating tag '{tag_name}': {str(e)}"
            return False, error_message, {}


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

        print(f"  Processing {len(tags_list)} tags with {self.max_workers} workers")
        tag_results = {}
        tags_processed = 0
        tags_successful = 0
        tags_failed = 0

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            # Submit all tasks
            future_to_tag = {
                executor.submit(
                    self.tag_evaluator.process_single_tag,
                    article_id,
                    file_name,
                    text,
                    tag_data,
                ): tag_data
                for tag_data in tags_list
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_tag):
                tag_data = future_to_tag[future]
                tag_id, tag_name, _ = tag_data
                tags_processed += 1

                try:
                    success, message, result = future.result()
                    if success:
                        tag_results.update(result)
                        tags_successful += 1
                        print(f"  [{tags_processed}/{len(tags_list)}] {message}")
                    else:
                        tags_failed += 1
                        print(
                            f"  [{tags_processed}/{len(tags_list)}] Failed: {message}"
                        )
                except Exception as e:
                    tags_failed += 1
                    print(
                        f"  [{tags_processed}/{len(tags_list)}] Error processing tag '{tag_name}': {str(e)}"
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
            print(f"Tagging article: {file_name}")

            # Find the article path
            file_paths = getArticlePathsForQuery(
                "*", [], self.articles_path, fileName=file_name
            )
            if not file_paths:
                print(f"  Could not find article file: {file_name}")
                continue

            file_path = file_paths[0]

            # Get tags that need to be evaluated for this article
            tags_to_evaluate = self._get_tags_for_article(article_id, active_tag_ids)

            if not tags_to_evaluate:
                print(f"  No tags to evaluate for this article")
                continue

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
                except Exception as e:
                    print(f"  Error extracting text from {file_name}: {str(e)}")
                    article_text = None

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
