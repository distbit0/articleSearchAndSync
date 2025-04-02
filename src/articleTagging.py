import os
import sys
import json
import traceback
import argparse
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Set, Optional
from loguru import logger
from dotenv import load_dotenv
from openai import OpenAI
from .utils import getConfig
from . import db
from . import textExtraction

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

    def __init__(self):
        pass

    def _with_connection(self):
        return db.get_connection()

    def sync_tags_from_config(self) -> None:
        """Synchronize tag definitions from config.json into the database."""
        config = getConfig()
        db.sync_tags_from_config(config)


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

    def _create_openai_client(self) -> OpenAI:
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

    def evaluate_tags(self, text: str, tags_to_evaluate: List) -> Dict[int, bool]:
        if not text or not text.strip():
            logger.warning("No text to evaluate for tags")
            return {tag["id"]: False for tag in tags_to_evaluate}
        if not tags_to_evaluate:
            return {}

        # Assume tags_to_evaluate has only a single element
        tag = tags_to_evaluate[0]
        client = self._create_openai_client()

        # Only include the description in the prompt, with no mention of tag name
        tag_description = tag["description"]

        logger.debug(f"Evaluating article for a single tag using model: {self.model}")

        system_prompt = (
            "Your task is to determine if the article text matches the provided description."
            "Interpret the description literally. You MUST respond in valid JSON format only."
        )

        # Simple JSON format with a single boolean response
        json_format_example = '{"matches": true or false}'

        user_prompt = (
            f"Please analyze the following article text to determine if it matches the description provided below.\n\n"
            f"Interpret the description literally.\n\nDescription: {tag_description}\n\n"
            f"Text to evaluate:\n{text[:6000]}\n\n"
            f"Based on the description, state if this text matches the description.\n\n"
            f"Your response must be valid JSON in this exact format:\n{json_format_example}"
        )

        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                result_text = response.choices[0].message.content.strip()
                result_json = json.loads(result_text)

                # Map the result to the tag ID
                match_result = result_json.get("matches", False)
                results = {tag["id"]: match_result}

                logger.debug(f"Tag evaluation result: {match_result}")

                if tag["id"] == 487 and match_result == True:
                    print("\n\n\n", user_prompt, results)

                return results
            except json.JSONDecodeError as e:
                retry_count += 1
                logger.warning(
                    f"Attempt {retry_count}: Failed to parse JSON response: {result_text}"
                )
                if retry_count >= max_retries:
                    logger.error(f"All {max_retries} attempts failed. Last error: {e}")
                    return {tag["id"]: False}
                user_prompt = (
                    f"The previous response couldn't be parsed as valid JSON. The error was: {e}\n\n{user_prompt}\n\n"
                    "IMPORTANT: YOU MUST RETURN ONLY VALID JSON. No explanations or additional text."
                )
            except Exception as e:
                logger.error(f"Error evaluating tags: {e}\n{traceback.format_exc()}")
                return {tag["id"]: False}

    def batch_evaluate_tags(
        self, article_id: int, file_name: str, text: str, tags_to_evaluate: List
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
                batch_tag_names = [tag["name"] for tag in batch]
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

    def __init__(self):
        self.config = getConfig()
        self.articles_path = self.config.get("articleFileFolder", "")
        self.max_articles_per_session = int(
            self.config.get("maxArticlesToTagPerSession", 100)
        )
        self.max_tagging_threads = int(self.config.get("llm_api_batch_size", 4))
        self.tag_evaluator = TagEvaluator()
        self.tag_article_match_cache = {}
        self.tag_details_cache = {}
        self._cache_tag_search_results()

    def _get_active_tag_ids(self) -> Set[int]:
        """Get the IDs of all active tags that should be applied to articles."""
        active_tag_ids = set()
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT id, name FROM tags")
            for tag_id, tag_name in cursor.fetchall():
                active_tag_ids.add(tag_id)
        return active_tag_ids

    def _get_articles_needing_tagging(self) -> List[Tuple[int, str, str, str]]:
        """Get articles that need tagging."""
        return db.get_articles_needing_tagging(self.max_articles_per_session)

    def _get_tags_for_article(self, file_name: str, active_tag_ids: Set[int]) -> List:
        """Get tags that need to be evaluated for an article."""
        tags_to_evaluate = []
        for tag_id in active_tag_ids:
            if tag_id in self.tag_details_cache:
                tag = self.tag_details_cache[tag_id]
                matchingArticles = self.tag_article_match_cache.get(tag_id)
                if (
                    matchingArticles is None or file_name in matchingArticles
                ):  # if tag not in dict, tag has no filters
                    tags_to_evaluate.append(tag)
        return tags_to_evaluate

    def _get_tag_criteria_cache_key(self, any_tags, and_tags, not_any_tags) -> str:
        """Create a cache key for tag search criteria."""
        any_tags_str = "|".join(sorted(any_tags)) if any_tags else ""
        and_tags_str = "|".join(sorted(and_tags)) if and_tags else ""
        not_any_tags_str = "|".join(sorted(not_any_tags)) if not_any_tags else ""
        return f"{any_tags_str}#{and_tags_str}#{not_any_tags_str}"

    def _cache_tag_search_results(self) -> None:
        """Cache tag search criteria for tags that have filtering (any/and/not)."""
        self.tag_details_cache = db.get_all_tag_details()
        for tag in self.tag_details_cache.values():
            if tag["any_tags"] or tag["and_tags"] or tag["not_any_tags"]:
                articlesMatchingTag = db.searchArticlesByTags(
                    any_tags=tag["any_tags"],
                    and_tags=tag["and_tags"],
                    not_any_tags=tag["not_any_tags"],
                )
                self.tag_article_match_cache[tag["id"]] = articlesMatchingTag

    def _prepare_article_work_units(
        self, article: Tuple[int, str, str, str], active_tag_ids: Set[int]
    ) -> List[Dict]:
        """Prepare work units for an article to be processed for content tagging."""
        article_id, file_hash, file_name, summary = article
        tags_to_evaluate = self._get_tags_for_article(file_name, active_tag_ids)
        work_units = []

        if not tags_to_evaluate:
            return work_units

        # Split tags based on use_summary attribute
        summary_tags = [
            tag for tag in tags_to_evaluate if tag.get("use_summary", False)
        ]
        full_text_tags = [
            tag for tag in tags_to_evaluate if not tag.get("use_summary", False)
        ]

        # Create work unit for tags that use summary
        if summary_tags and summary:
            work_units.append(
                {
                    "article_id": article_id,
                    "file_name": file_name,
                    "text": summary,
                    "tags": summary_tags,
                }
            )

        # Create work unit for tags that need full text
        if full_text_tags:
            try:
                file_path = os.path.join(self.articles_path, file_name)
                # Use default max_words if not specified
                max_words = int(self.config.get("summary_in_max_words", 3000))
                text, extraction_method, word_count = (
                    textExtraction.extract_text_from_file(file_path, max_words)
                )
                work_units.append(
                    {
                        "article_id": article_id,
                        "file_name": file_name,
                        "text": text,
                        "tags": full_text_tags,
                    }
                )
            except Exception as e:
                logger.error(f"Error extracting text from {file_path}: {str(e)}")

        return work_units

    def _process_article_tag_batch(
        self, article_id: int, file_name: str, text: str, tags_batch: List
    ) -> Dict[int, bool]:
        """Process a batch of tags for an article."""
        logger.debug(f"Evaluating article {file_name} with {len(tags_batch)} tags")
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
        for article_id, results in results_by_article.items():
            for tag_id in results.get("matches", {}):
                db.set_article_tag(article_id, tag_id, True)
            for tag_id in results.get("non_matches", {}):
                db.set_article_tag(article_id, tag_id, False)

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

        all_work_units = []
        for article in articles:
            work_units = self._prepare_article_work_units(article, active_tag_ids)
            all_work_units.extend(work_units)
        logger.info(f"Created {len(all_work_units)} work units")

        if all_work_units:
            results_by_article = self._process_work_units(all_work_units)
            self._apply_tag_results_to_articles(results_by_article)

            # Initialize tagStats before processing any tags
            tagStats = {}
            # First, count all direct tag matches from content-based tagging
            for _, results in results_by_article.items():
                for tag_id in results.get("matches", {}):
                    tagStats[tag_id] = tagStats.get(tag_id, 0) + 1

            for tag_id, count in tagStats.items():
                tag_details = self.tag_details_cache.get(tag_id)
                if tag_details:
                    logger.info(f"Tag {tag_details['name']}: {count} articles")

        logger.info("Tagging process completed")


def analyze_tag_results(tag_name: str) -> None:
    """Analyze which articles match or do not match a specific tag and output a markdown report."""
    tag_id = db.get_tag_id_by_name(tag_name)
    if not tag_id:
        logger.error(f"Tag not found: {tag_name}")
        return
    matching_articles = db.get_articles_by_tag(tag_name)
    non_matching_articles = db.get_articles_not_matching_tag(tag_name)
    report = f"# Tag Analysis: {tag_name}\n\n"
    report += f"## Matching Articles ({len(matching_articles)})\n\n"
    for file_name in matching_articles:
        report += f"- {file_name}\n"
    report += f"\n## Non-Matching Articles ({len(non_matching_articles)})\n\n"
    for file_name in non_matching_articles:
        report += f"- {file_name}\n"
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage",
        f"tag_analysis_{tag_name}.md",
    )
    with open(report_path, "w") as f:
        f.write(report)
    logger.info(f"Tag analysis saved to: {report_path}")


def main(all_tags=True, limit=None, analyze=None, debug=False):
    """
    Main entry point for the tagging process.

    Args:
        all_tags: Create content tags.
        limit: Limit the number of articles to process.
        analyze: Analyze a specific tag.
        debug: Enable debug logging.
    """
    load_environment_variables()
    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="Manage article tags.")
        parser.add_argument("--all", action="store_true", help="Create content tags")
        parser.add_argument(
            "--limit", type=int, help="Limit the number of articles to process"
        )
        parser.add_argument("--analyze", type=str, help="Analyze a specific tag")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        args = parser.parse_args()
        all_tags = args.all
        limit = args.limit
        analyze = args.analyze
        debug = args.debug

    if debug:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")

    if analyze:
        analyze_tag_results(analyze)
        return

    tag_manager = TagManager()
    tag_manager.sync_tags_from_config()
    logger.info("Tags synced from config")

    if all_tags:
        logger.info("Applying content-based tags...")
        article_tagger = ArticleTagger()
        article_tagger.apply_tags_to_articles()
        logger.info("Content tagging completed")


if __name__ == "__main__":
    main()
