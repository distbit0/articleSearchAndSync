import os
import sys
import json
import hashlib
import traceback
import time
import argparse
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set, Optional
from loguru import logger
from dotenv import load_dotenv
from openai import OpenAI
from .utils import getConfig, searchArticlesByTags
from .textExtraction import extract_text_from_file
from . import db
import re

# Constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE_PATH = LOG_DIR / "tagging.log"

LOG_DIR.mkdir(exist_ok=True, parents=True)

# Configure loguru logger
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add(
    LOG_FILE_PATH,
    rotation="5 MB",
    retention=3,
    level="WARNING",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
)


def load_environment_variables() -> None:
    """Load environment variables from a .env file."""
    for env_path in [PROJECT_ROOT / ".env", Path.cwd() / ".env", Path(".env")]:
        if env_path.exists():
            load_dotenv(dotenv_path=str(env_path))
            break


def setup_tag_database() -> str:
    """Setup the SQLite database and create necessary tables."""
    return db.setup_database()


class TagManager:
    """Handle database operations for article tags."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _with_connection(self):
        return db.get_connection()

    def sync_tags_from_config(self) -> None:
        """Synchronize tag definitions from config.json into the database."""
        config = getConfig()
        db.sync_tags_from_config(config)

    def _get_excluded_folders(self) -> Set[str]:
        """Get list of folders that should be excluded from folder tagging."""
        config = getConfig()
        # Use "excludedFolders" (or "folderTagExclusions" if that’s what you prefer)
        return set(config.get("excludedFolders", []))

    def _fetch_existing_tags(self, cursor) -> Dict[str, Dict[str, int]]:
        """Fetch all existing folder and prev_folder tags from the database."""
        folder_tags = {}
        prev_folder_tags = {}
        for tag_id, tag_name in db.get_folder_tags():
            if tag_name.startswith("folder_"):
                # Remove the 'folder_' prefix for matching purposes
                folder_tags[tag_name[7:]] = tag_id
            elif tag_name.startswith("prev_folder_"):
                prev_folder_tags[tag_name[12:]] = tag_id
        return {"folder_tags": folder_tags, "prev_folder_tags": prev_folder_tags}

    def _get_articles(
        self, cursor, max_articles: Optional[int], debug: bool
    ) -> List[Tuple]:
        """Get articles from database to process for folder tagging."""
        all_articles = db.get_all_articles()
        if max_articles:
            if debug:
                logger.info(f"Limiting folder tagging to {max_articles} articles")
            all_articles = all_articles[:max_articles]
        return all_articles

    def _get_current_article_tags(self, cursor) -> Dict[int, Dict]:
        """Get a dictionary mapping article IDs to their current folder tag associations."""
        article_tags = db.get_current_article_tags()
        # Transform to a simple format (set of tag IDs for each article)
        result = {}
        for article_id, tags_dict in article_tags.items():
            result[article_id] = {
                "matching": {tag_id for tag_id, _ in tags_dict.get("matching", [])},
                "not_matching": {
                    tag_id for tag_id, _ in tags_dict.get("not_matching", [])
                },
            }
        return result

    def _process_articles(
        self,
        articles: List[Tuple],
        articles_path: str,
        exclusions: Set[str],
        current_article_tags: Dict,
        folder_tags: Dict[str, int],
        prev_folder_tags: Dict[str, int],
    ) -> Tuple[Dict[str, Set[int]], Dict[str, Set[int]]]:
        """
        Process articles and collect folder information.
        Returns two dictionaries:
          - article_folders: mapping folder (relative path) to set of article IDs
          - article_prev_folders: mapping parent folder (relative path) to set of article IDs
        """
        article_folders = {}
        article_prev_folders = {}

        for article_id, file_name in articles:
            try:
                relative_folder = os.path.dirname(file_name)
                if not relative_folder:
                    continue
                # Normalize folder path
                relative_folder = relative_folder.replace("\\", "/")
                if any(excl in relative_folder for excl in exclusions):
                    continue

                # Direct folder: add article_id under this folder key
                article_folders.setdefault(relative_folder, set()).add(article_id)

                # Also process parent folders (if any)
                path_parts = relative_folder.split("/")
                for i in range(1, len(path_parts)):
                    prev_folder = "/".join(path_parts[:i])
                    if prev_folder and not any(
                        excl in prev_folder for excl in exclusions
                    ):
                        article_prev_folders.setdefault(prev_folder, set()).add(
                            article_id
                        )
            except Exception as e:
                logger.error(f"Error processing article {file_name}: {e}")

        return article_folders, article_prev_folders

    def _batch_create_tags(
        self,
        cursor,
        tags_to_create: set,
        tags_dict: Dict[str, int],
        folder_locations: Dict[str, Set[int]],
        is_prev: bool,
        debug: bool,
    ) -> None:
        """Create folder tags in batches and update article-tag relationships."""
        prefix = "prev_folder_" if is_prev else "folder_"

        for folder_name in tags_to_create:
            tag_name = f"{prefix}{folder_name}"
            description = f"{'Parent folder' if is_prev else 'Folder'}: {folder_name}"

            tag_id = db.get_tag_id_by_name(tag_name)
            if not tag_id:
                # Create the tag if it doesn't exist
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO tags (name, description, use_summary) VALUES (?, ?, ?)",
                        (tag_name, description, False),
                    )
                    tag_id = cursor.lastrowid
                    conn.commit()
                tags_dict[folder_name] = tag_id
                if debug:
                    logger.debug(f"Created tag: {tag_name} with ID {tag_id}")

            # For each article in this folder, assign the tag
            for article_id in folder_locations.get(folder_name, set()):
                db.set_article_tag(article_id, tag_id, True)
                if debug:
                    logger.debug(f"Tagged article {article_id} with {tag_name}")

    def create_folder_tags(
        self,
        articles_path: str,
        max_articles: Optional[int] = None,
        debug: bool = False,
    ) -> Dict[str, Dict[str, int]]:
        """Create and update folder tags based on article file locations."""
        logger.info("Creating folder tags...")
        exclusions = self._get_excluded_folders()
        if debug:
            logger.debug(f"Excluded folders: {exclusions}")

        with db.get_connection() as conn:
            cursor = conn.cursor()
            tag_dict = self._fetch_existing_tags(cursor)
            folder_tags = tag_dict["folder_tags"]
            prev_folder_tags = tag_dict["prev_folder_tags"]

            if debug:
                logger.debug(f"Found {len(folder_tags)} existing folder tags")
                logger.debug(f"Found {len(prev_folder_tags)} existing prev_folder tags")

            articles = self._get_articles(cursor, max_articles, debug)
            if debug:
                logger.debug(f"Found {len(articles)} articles to process")
            current_article_tags = self._get_current_article_tags(cursor)

            article_folders, article_prev_folders = self._process_articles(
                articles,
                articles_path,
                exclusions,
                current_article_tags,
                folder_tags,
                prev_folder_tags,
            )
            if debug:
                logger.debug(f"Found {len(article_folders)} unique folders")
                logger.debug(f"Found {len(article_prev_folders)} unique parent folders")

            folder_tags_to_create = set(article_folders.keys()) - set(
                folder_tags.keys()
            )
            self._batch_create_tags(
                cursor,
                folder_tags_to_create,
                folder_tags,
                article_folders,
                False,
                debug,
            )

            prev_folder_tags_to_create = set(article_prev_folders.keys()) - set(
                prev_folder_tags.keys()
            )
            self._batch_create_tags(
                cursor,
                prev_folder_tags_to_create,
                prev_folder_tags,
                article_prev_folders,
                True,
                debug,
            )

        logger.info("Folder tags created successfully")
        return {"folder_tags": folder_tags, "prev_folder_tags": prev_folder_tags}


class TagEvaluator:
    """Evaluate whether an article matches given tag descriptions using OpenRouter API."""

    def __init__(self):
        self.config = getConfig()
        self.model = self.config.get("ai_model", "google/gemini-2.0-flash-001")
        self.batch_size = int(self.config.get("tag_batch_size", 3))
        logger.info(f"Tag batch size set to {self.batch_size}")
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.error("OPENROUTER_API_KEY not found in environment variables")
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        self.referer = os.getenv("OPENROUTER_REFERER", "articleSearchAndSync")
        self.title = os.getenv("OPENROUTER_TITLE", "Article Search and Sync")

    def _create_openai_client(self) -> OpenAI:
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            default_headers={"HTTP-Referer": self.referer, "X-Title": self.title},
        )

    def evaluate_tags(
        self, text: str, tags_to_evaluate: List[Tuple[int, str, str]]
    ) -> Dict[int, bool]:
        if not text or not text.strip():
            logger.warning("No text to evaluate for tags")
            return {tag_id: False for tag_id, _, _ in tags_to_evaluate}
        if not tags_to_evaluate:
            return {}
        client = self._create_openai_client()
        tag_info = "\n\n".join(
            [
                f"Tag {i+1}:\n- Name: {tag_name}\n- Description: {tag_description}"
                for i, (_, tag_name, tag_description) in enumerate(tags_to_evaluate)
            ]
        )
        tag_names = [tag_name for _, tag_name, _ in tags_to_evaluate]
        logger.debug(
            f"Evaluating article for tags: {', '.join(tag_names)} using model: {self.model}"
        )
        system_prompt = (
            "You are a helpful system that evaluates whether a text matches given tag descriptions. "
            "Your task is to determine if the article text is described by each of the provided tag descriptions. "
            "Interpret them literally. You MUST respond in valid JSON format only."
        )
        json_format_example = (
            "{\n"
            + ",\n".join([f'  "{tag}": true or false' for tag in tag_names])
            + "\n}"
        )
        user_prompt = (
            f"Please analyze the following text to determine if it matches/is described by each of the tag descriptions provided below. "
            f"Interpret the tag descriptions literally.\n\nTags to evaluate:\n\n{tag_info}\n\n"
            f"Text to evaluate:\n{text[:6000]}  # Limit text length to avoid token limits\n\n"
            f"Based on the tag descriptions, determine if this text matches each tag.\n"
            f"Your response must be valid JSON in this exact format:\n{json_format_example}"
        )
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = client.chat.completions.create(
                    extra_headers={"HTTP-Referer": self.referer, "X-Title": self.title},
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                result_text = response.choices[0].message.content.strip()
                result_json = json.loads(result_text)
                results = {
                    tag_id: result_json.get(tag_name, False)
                    for tag_id, tag_name, _ in tags_to_evaluate
                }
                logger.debug(f"Tag evaluation results: {result_json}")
                return results
            except json.JSONDecodeError as e:
                retry_count += 1
                logger.warning(
                    f"Attempt {retry_count}: Failed to parse JSON response: {result_text}"
                )
                if retry_count >= max_retries:
                    logger.error(f"All {max_retries} attempts failed. Last error: {e}")
                    return {tag_id: False for tag_id, _, _ in tags_to_evaluate}
                user_prompt = (
                    f"The previous response couldn't be parsed as valid JSON. The error was: {e}\n\n{user_prompt}\n\n"
                    "IMPORTANT: YOU MUST RETURN ONLY VALID JSON. No explanations or additional text."
                )
            except Exception as e:
                logger.error(f"Error evaluating tags: {e}\n{traceback.format_exc()}")
                return {tag_id: False for tag_id, _, _ in tags_to_evaluate}

    def batch_evaluate_tags(
        self,
        article_id: int,
        file_name: str,
        text: str,
        tags_to_evaluate: List[Tuple[int, str, str]],
    ) -> Dict[int, bool]:
        if not tags_to_evaluate or not text:
            return {}
        tag_batches = [
            tags_to_evaluate[i : i + self.batch_size]
            for i in range(0, len(tags_to_evaluate), self.batch_size)
        ]
        logger.debug(
            f"Processing {len(tags_to_evaluate)} tags in {len(tag_batches)} batches (batch size: {self.batch_size})"
        )
        tag_results = {}
        for i, batch in enumerate(tag_batches):
            try:
                batch_tag_names = [tag_name for _, tag_name, _ in batch]
                logger.debug(
                    f"Batch {i+1}/{len(tag_batches)}: Evaluating tags {', '.join(batch_tag_names)}"
                )
                batch_results = self.evaluate_tags(text, batch)
                tag_results.update(batch_results)
                logger.debug(f"Batch {i+1}/{len(tag_batches)}: Completed evaluation")
            except Exception as e:
                logger.error(f"Error processing batch {i+1}: {e}")
        return tag_results


class ArticleTagger:
    """Manage applying tags to articles using parallel processing and AI evaluation."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.config = getConfig()
        self.articles_path = self.config.get("articleFileFolder", "")
        self.max_articles_per_session = int(
            self.config.get("maxArticlesToTagPerSession", 100)
        )
        self.max_tagging_threads = int(self.config.get("llm_api_batch_size", 4))
        self.tag_evaluator = TagEvaluator()
        self.tag_search_cache = {}

    def _get_active_tag_ids(self) -> Set[int]:
        """Get the IDs of all active tags that should be applied to articles."""
        active_tag_ids = set()
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM tags")
            for tag_id, tag_name in cursor.fetchall():
                if not tag_name.startswith("folder_") and not tag_name.startswith(
                    "prev_folder_"
                ):
                    active_tag_ids.add(tag_id)
        return active_tag_ids

    def _get_articles_needing_tagging(self) -> List[Tuple[int, str, str, str]]:
        """Get articles that need tagging."""
        return db.get_articles_needing_tagging(self.max_articles_per_session)

    def _get_tags_for_article(
        self, article_id: int, active_tag_ids: Set[int]
    ) -> List[Tuple[int, str, str]]:
        """Get tags that need to be evaluated for an article."""
        tags_to_evaluate = []
        with db.get_connection() as conn:
            cursor = conn.cursor()
            tag_details = db.get_all_tag_details()
            for tag_id in active_tag_ids:
                if tag_id in tag_details:
                    tag = tag_details[tag_id]
                    # Skip tags with filtering criteria (handled separately)
                    if (
                        tag.get("any_tags")
                        or tag.get("and_tags")
                        or tag.get("not_any_tags")
                    ):
                        continue
                    tags_to_evaluate.append((tag_id, tag["name"], tag["description"]))
        return tags_to_evaluate

    def _get_tag_criteria_cache_key(self, any_tags, and_tags, not_any_tags) -> str:
        """Create a cache key for tag search criteria."""
        any_tags_str = "|".join(sorted(any_tags)) if any_tags else ""
        and_tags_str = "|".join(sorted(and_tags)) if and_tags else ""
        not_any_tags_str = "|".join(sorted(not_any_tags)) if not_any_tags else ""
        return f"{any_tags_str}#{and_tags_str}#{not_any_tags_str}"

    def _prepare_article_work_units(
        self, article: Tuple[int, str, str, str], active_tag_ids: Set[int]
    ) -> List[Dict]:
        """Prepare work units for an article to be processed for content tagging."""
        article_id, file_hash, file_name, summary = article
        tags_to_evaluate = self._get_tags_for_article(article_id, active_tag_ids)
        work_units = []
        if tags_to_evaluate:
            file_path = os.path.join(self.articles_path, file_name)
            try:
                if os.path.exists(file_path):
                    article_text = summary
                    if not article_text:
                        # Extract text if summary is missing
                        article_text, _, _ = extract_text_from_file(file_path)
                    work_units.append(
                        {
                            "article_id": article_id,
                            "file_name": file_name,
                            "text": article_text,
                            "tags": tags_to_evaluate,
                        }
                    )
                else:
                    logger.warning(f"File not found: {file_path}")
            except Exception as e:
                logger.error(f"Error extracting text from {file_path}: {e}")
        return work_units

    def _process_article_tag_batch(
        self,
        article_id: int,
        file_name: str,
        text: str,
        tags_batch: List[Tuple[int, str, str]],
    ) -> Dict[int, bool]:
        """Process a batch of tags for an article."""
        logger.info(f"Evaluating article {file_name} with {len(tags_batch)} tags")
        try:
            return self.tag_evaluator.batch_evaluate_tags(
                article_id, file_name, text, tags_batch
            )
        except Exception as e:
            logger.error(f"Error evaluating article {file_name}: {e}")
            logger.error(traceback.format_exc())
            return {}

    def _process_work_units(self, work_units: List[Dict]) -> Dict[int, Dict]:
        """Process all work units in parallel using a ThreadPoolExecutor."""
        if not work_units:
            logger.debug("No work units to process")
            return {}
        logger.info(f"Processing {len(work_units)} work units in parallel")
        results_by_article = {}
        file_names_by_article = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_tagging_threads
        ) as executor:
            futures = {}
            for unit in work_units:
                article_id = unit["article_id"]
                file_name = unit["file_name"]
                file_names_by_article[article_id] = file_name
                text = unit["text"]
                # Submit the work unit for parallel processing
                future = executor.submit(
                    self._process_article_tag_batch,
                    article_id,
                    file_name,
                    text,
                    unit["tags"],
                )
                futures[future] = article_id
            for future in concurrent.futures.as_completed(futures):
                article_id = futures[future]
                try:
                    batch_results = future.result()
                    if article_id not in results_by_article:
                        results_by_article[article_id] = {
                            "matches": {},
                            "non_matches": {},
                        }
                    for tag_id, matched in batch_results.items():
                        if matched:
                            results_by_article[article_id]["matches"][tag_id] = True
                        else:
                            results_by_article[article_id]["non_matches"][tag_id] = True
                except Exception as e:
                    logger.error(
                        f"Error processing article {article_id}: {e}\n{traceback.format_exc()}"
                    )
        return results_by_article

    def _apply_tag_results_to_articles(
        self, results_by_article: Dict[int, Dict]
    ) -> None:
        """Apply tag evaluation results to articles in the database."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            for article_id, results in results_by_article.items():
                for tag_id in results.get("matches", {}):
                    db.set_article_tag(article_id, tag_id, True)
                for tag_id in results.get("non_matches", {}):
                    db.set_article_tag(article_id, tag_id, False)
            conn.commit()

    def _cache_tag_search_results(self, cursor) -> None:
        """Cache tag search criteria for tags that have filtering (any/and/not)."""
        self.tag_search_cache = {}
        tag_details = db.get_all_tag_details()
        for tag_id, tag in tag_details.items():
            any_tags = tag.get("any_tags", [])
            and_tags = tag.get("and_tags", [])
            not_any_tags = tag.get("not_any_tags", [])
            if any_tags or and_tags or not_any_tags:
                self.tag_search_cache[tag_id] = {
                    "name": tag["name"],
                    "any_tags": any_tags,
                    "and_tags": and_tags,
                    "not_any_tags": not_any_tags,
                }

    def apply_tags_to_articles(self) -> None:
        """Apply content-based tags to articles based on tag definitions."""
        logger.info("Starting tagging process...")
        articles = self._get_articles_needing_tagging()
        if not articles:
            logger.info("No articles need tagging")
            return
        logger.info(f"Found {len(articles)} articles for tagging")
        active_tag_ids = self._get_active_tag_ids()
        logger.info(f"Found {len(active_tag_ids)} active tags")

        with db.get_connection() as conn:
            cursor = conn.cursor()
            self._cache_tag_search_results(cursor)

        all_work_units = []
        for article in articles:
            work_units = self._prepare_article_work_units(article, active_tag_ids)
            all_work_units.extend(work_units)
        logger.info(f"Created {len(all_work_units)} work units")

        if all_work_units:
            results_by_article = self._process_work_units(all_work_units)
            self._apply_tag_results_to_articles(results_by_article)

            # Process tags with filtering criteria separately
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for article_id in results_by_article.keys():
                    article_tags = set(db.get_tags_for_article(article_id))
                    for tag_id, criteria in self.tag_search_cache.items():
                        tag_name = criteria["name"]
                        any_tags = set(criteria.get("any_tags", []))
                        and_tags = set(criteria.get("and_tags", []))
                        not_any_tags = set(criteria.get("not_any_tags", []))
                        any_tag_ids = {
                            db.get_tag_id_by_name(tag)
                            for tag in any_tags
                            if db.get_tag_id_by_name(tag)
                        }
                        and_tag_ids = {
                            db.get_tag_id_by_name(tag)
                            for tag in and_tags
                            if db.get_tag_id_by_name(tag)
                        }
                        not_any_tag_ids = {
                            db.get_tag_id_by_name(tag)
                            for tag in not_any_tags
                            if db.get_tag_id_by_name(tag)
                        }
                        match = True
                        if any_tag_ids and not any_tag_ids.intersection(article_tags):
                            match = False
                        if and_tag_ids and not and_tag_ids.issubset(article_tags):
                            match = False
                        if not_any_tag_ids and not_any_tag_ids.intersection(
                            article_tags
                        ):
                            match = False
                        db.set_article_tag(article_id, tag_id, match)
                conn.commit()

        logger.info("Tagging process completed")


def analyze_tag_results(tag_name: str) -> None:
    """Analyze which articles match or do not match a specific tag and output a markdown report."""
    db_path = db.get_db_path()
    tag_id = db.get_tag_id_by_name(tag_name)
    if not tag_id:
        logger.error(f"Tag not found: {tag_name}")
        return
    matching_articles = db.get_articles_by_tag(tag_name)
    non_matching_articles = db.get_articles_without_tag(tag_name)
    report = f"# Tag Analysis: {tag_name}\n\n"
    report += f"## Matching Articles ({len(matching_articles)})\n\n"
    for file_name in matching_articles:
        report += f"- {file_name}\n"
    report += f"\n## Non-Matching Articles ({len(non_matching_articles)})\n\n"
    for file_name in non_matching_articles:
        report += f"- {file_name}\n"
    report_path = os.path.join(os.path.dirname(db_path), f"tag_analysis_{tag_name}.md")
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Tag analysis saved to: {report_path}")


def main(folder_tags=False, all_tags=True, limit=None, analyze=None, debug=False):
    """
    Main entry point for the tagging process.

    Args:
        folder_tags: Create folder tags only.
        all_tags: Create both folder tags and content tags.
        limit: Limit the number of articles to process.
        analyze: Analyze a specific tag.
        debug: Enable debug logging.
    """
    load_environment_variables()
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="Manage article tags.")
        parser.add_argument(
            "--folder-tags", action="store_true", help="Create folder tags only"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Create both folder tags and content tags",
        )
        parser.add_argument(
            "--limit", type=int, help="Limit the number of articles to process"
        )
        parser.add_argument("--analyze", type=str, help="Analyze a specific tag")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        args = parser.parse_args()
        folder_tags = args.folder_tags
        all_tags = args.all
        limit = args.limit
        analyze = args.analyze
        debug = args.debug

    if debug:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")

    db_path = db.get_db_path()

    if analyze:
        analyze_tag_results(analyze)
        return

    tag_manager = TagManager(db_path)
    tag_manager.sync_tags_from_config()
    logger.info("Tags synced from config")

    if folder_tags or all_tags:
        logger.info("Creating folder tags...")
        article_folder = getConfig().get("articleFileFolder", "")
        if not os.path.exists(article_folder):
            logger.error(f"Article folder not found: {article_folder}")
            return
        tag_manager.create_folder_tags(article_folder, limit, debug)

    if all_tags:
        logger.info("Applying content-based tags...")
        article_tagger = ArticleTagger(db_path)
        article_tagger.apply_tags_to_articles()
        logger.info("Content tagging completed")


if __name__ == "__main__":
    main()
