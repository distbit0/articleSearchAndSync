import os
import sys
import json
import sqlite3
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

# Constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
DB_FILENAME = "article_summaries.db"
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
    STORAGE_DIR.mkdir(exist_ok=True)
    db_path = STORAGE_DIR / DB_FILENAME
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                use_summary BOOLEAN,
                any_tags TEXT,
                and_tags TEXT,
                not_any_tags TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS article_tags (
                article_id INTEGER,
                tag_id INTEGER,
                matches BOOLEAN NOT NULL DEFAULT 1,
                PRIMARY KEY (article_id, tag_id),
                FOREIGN KEY (article_id) REFERENCES article_summaries(id),
                FOREIGN KEY (tag_id) REFERENCES tags(id)
            );
            CREATE TABLE IF NOT EXISTS tag_hashes (
                tag_id INTEGER PRIMARY KEY,
                property_hash TEXT,
                FOREIGN KEY (tag_id) REFERENCES tags(id)
            );
        """
        )
        conn.commit()
    return str(db_path)


def get_tag_property_hash(
    description: str,
    use_summary: bool,
    any_tags: List[str] = None,
    and_tags: List[str] = None,
    not_any_tags: List[str] = None,
) -> str:
    """Compute an MD5 hash from tag properties."""
    any_tags_str = "|".join(sorted(any_tags or []))
    and_tags_str = "|".join(sorted(and_tags or []))
    not_any_tags_str = "|".join(sorted(not_any_tags or []))
    property_string = (
        f"{description}|{use_summary}|{any_tags_str}|{and_tags_str}|{not_any_tags_str}"
    )
    return hashlib.md5(property_string.encode()).hexdigest()


class TagManager:
    """Handle database operations for article tags."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _with_connection(self):
        return sqlite3.connect(self.db_path)

    def sync_tags_from_config(self) -> None:
        """Synchronize tag definitions from config.json into the database."""
        config = getConfig()
        tag_config = config.get("article_tags", {})
        if not tag_config:
            logger.error("No 'article_tags' section found in config.json")
            return
        with self._with_connection() as conn:
            cursor = conn.cursor()
            # Ensure filtering columns exist
            cursor.execute("PRAGMA table_info(tags)")
            columns = {row[1] for row in cursor.fetchall()}
            for col in ("any_tags", "and_tags", "not_any_tags"):
                if col not in columns:
                    cursor.execute(f"ALTER TABLE tags ADD COLUMN {col} TEXT")
            # Load existing tags
            cursor.execute(
                "SELECT id, name, description, use_summary, any_tags, and_tags, not_any_tags FROM tags"
            )
            existing_tags = {
                row[1]: {
                    "id": row[0],
                    "description": row[2],
                    "use_summary": bool(row[3]),
                    "any_tags": json.loads(row[4]) if row[4] else [],
                    "and_tags": json.loads(row[5]) if row[5] else [],
                    "not_any_tags": json.loads(row[6]) if row[6] else [],
                }
                for row in cursor.fetchall()
            }
            # Load property hashes for existing tags
            cursor.execute("SELECT tag_id, property_hash FROM tag_hashes")
            property_hashes = {row[0]: row[1] for row in cursor.fetchall()}
            # Process each tag from config
            for tag_name, tag_data in tag_config.items():
                if isinstance(tag_data, list):
                    continue
                description = tag_data.get("description", "")
                use_summary = tag_data.get("use_summary", True)
                any_tags = tag_data.get("any_tags", [])
                and_tags = tag_data.get("and_tags", [])
                not_any_tags = tag_data.get("not_any_tags", [])
                new_hash = get_tag_property_hash(
                    description, use_summary, any_tags, and_tags, not_any_tags
                )
                if tag_name in existing_tags:
                    tag_id = existing_tags[tag_name]["id"]
                    if property_hashes.get(tag_id) != new_hash:
                        cursor.execute(
                            """UPDATE tags SET description = ?, use_summary = ?, any_tags = ?, and_tags = ?, not_any_tags = ?, 
                               last_updated = CURRENT_TIMESTAMP WHERE id = ?""",
                            (
                                description,
                                use_summary,
                                json.dumps(any_tags) if any_tags else None,
                                json.dumps(and_tags) if and_tags else None,
                                json.dumps(not_any_tags) if not_any_tags else None,
                                tag_id,
                            ),
                        )
                        if property_hashes.get(tag_id):
                            cursor.execute(
                                "UPDATE tag_hashes SET property_hash = ? WHERE tag_id = ?",
                                (new_hash, tag_id),
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO tag_hashes (tag_id, property_hash) VALUES (?, ?)",
                                (tag_id, new_hash),
                            )
                        cursor.execute(
                            "DELETE FROM article_tags WHERE tag_id = ?", (tag_id,)
                        )
                        logger.debug(
                            f"Updated tag '{tag_name}' and cleared previous assignments"
                        )
                else:
                    cursor.execute(
                        "INSERT INTO tags (name, description, use_summary, any_tags, and_tags, not_any_tags) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            tag_name,
                            description,
                            use_summary,
                            json.dumps(any_tags) if any_tags else None,
                            json.dumps(and_tags) if and_tags else None,
                            json.dumps(not_any_tags) if not_any_tags else None,
                        ),
                    )
                    tag_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO tag_hashes (tag_id, property_hash) VALUES (?, ?)",
                        (tag_id, new_hash),
                    )
                    logger.debug(f"Added new tag '{tag_name}'")
            conn.commit()

    def _initialize_db(self, cursor: sqlite3.Cursor) -> None:
        """Create indexes to improve performance."""
        cursor.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_article_summaries_file_name ON article_summaries(file_name);
            CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
            CREATE INDEX IF NOT EXISTS idx_article_tags_article_id ON article_tags(article_id);
            CREATE INDEX IF NOT EXISTS idx_article_tags_tag_id ON article_tags(tag_id);
        """
        )

    def _get_excluded_folders(self) -> Set[str]:
        return set(getConfig().get("folderTagExclusions", []))

    def _fetch_existing_tags(
        self, cursor: sqlite3.Cursor
    ) -> Tuple[Dict[str, int], Dict[str, int]]:
        cursor.execute(
            "SELECT id, name FROM tags WHERE name LIKE 'folder_%' OR name LIKE 'prev_folder_%'"
        )
        folder_tags = {}
        prev_folder_tags = {}
        for tag_id, name in cursor.fetchall():
            if name.startswith("folder_"):
                folder_tags[name] = tag_id
            elif name.startswith("prev_folder_"):
                prev_folder_tags[name] = tag_id
        return folder_tags, prev_folder_tags

    def _get_articles(
        self, cursor: sqlite3.Cursor, max_articles: Optional[int], debug: bool
    ) -> List[Tuple]:
        cursor.execute("SELECT id, file_name FROM article_summaries")
        articles = cursor.fetchall()
        if max_articles and len(articles) > max_articles:
            if debug:
                logger.debug(f"Limiting to {max_articles} articles")
            articles = articles[:max_articles]
        if debug:
            logger.debug(f"Processing {len(articles)} articles for folder tagging")
        return articles

    def _get_current_article_tags(self, cursor: sqlite3.Cursor) -> Dict[int, Dict]:
        cursor.execute(
            """SELECT at.article_id, t.name, t.id 
               FROM article_tags at
               JOIN tags t ON at.tag_id = t.id 
               WHERE t.name LIKE 'folder_%'"""
        )
        article_tags = {}
        for article_id, tag_name, tag_id in cursor.fetchall():
            article_tags.setdefault(article_id, {})[tag_name] = tag_id
        return article_tags

    def _process_articles(
        self,
        articles: List[Tuple],
        articles_path: str,
        exclusions: Set[str],
        current_article_tags: Dict,
        folder_tags: Dict[str, int],
        prev_folder_tags: Dict[str, int],
    ) -> Tuple[Any, Any, Any, Any, Any, Any]:
        folder_locations = {}
        tags_to_create = set()
        prev_tags_to_create = set()
        article_tag_associations = []
        article_prev_tag_associations = []
        article_keep_tags = {}
        for article_id, file_name in articles:
            if not file_name:
                continue
            keep_tags = set()
            article_folders = set()
            file_path = os.path.join(articles_path, file_name)
            rel_path = os.path.relpath(file_path, articles_path)
            folder_path = os.path.dirname(rel_path)
            if folder_path:
                current_path = ""
                for folder in Path(folder_path).parts:
                    if folder in exclusions or not folder:
                        continue
                    current_path = (
                        f"{current_path}/{folder}" if current_path else folder
                    )
                    article_folders.add(current_path)
                    folder_tag = f"folder_{current_path}"
                    keep_tags.add(folder_tag)
                    if folder_tag in folder_tags:
                        article_tag_associations.append(
                            (article_id, folder_tags[folder_tag])
                        )
                    else:
                        tags_to_create.add(
                            (
                                folder_tag,
                                f"Articles located in the '{current_path}' folder",
                            )
                        )
                    prev_tag = f"prev_folder_{current_path}"
                    if prev_tag in prev_folder_tags:
                        article_prev_tag_associations.append(
                            (article_id, prev_folder_tags[prev_tag])
                        )
                    else:
                        prev_tags_to_create.add(
                            (
                                prev_tag,
                                f"Articles previously located in the '{current_path}' folder",
                            )
                        )
                folder_locations[article_id] = article_folders
                article_keep_tags[article_id] = keep_tags
        tags_to_remove = []
        for article_id, current_tags in current_article_tags.items():
            keep = article_keep_tags.get(article_id, set())
            for tag_name, tag_id in current_tags.items():
                if tag_name.startswith("folder_") and tag_name not in keep:
                    tags_to_remove.append((article_id, tag_id))
        return (
            folder_locations,
            tags_to_create,
            prev_tags_to_create,
            article_tag_associations,
            article_prev_tag_associations,
            tags_to_remove,
        )

    def _batch_create_tags(
        self,
        cursor: sqlite3.Cursor,
        tags_to_create: set,
        tags_dict: Dict[str, int],
        folder_locations: Dict[int, set],
        is_prev: bool,
        debug: bool,
    ) -> List[Tuple[int, int]]:
        new_associations = []
        for name, desc in tags_to_create:
            cursor.execute(
                "INSERT OR IGNORE INTO tags (name, description, use_summary) VALUES (?, ?, 1)",
                (name, desc),
            )
            cursor.execute("SELECT id FROM tags WHERE name = ?", (name,))
            tag_id = cursor.fetchone()[0]
            tags_dict[name] = tag_id
            folder_key = name[12:] if is_prev else name[7:]
            for article_id, folders in folder_locations.items():
                if folder_key in folders:
                    new_associations.append((article_id, tag_id))
        tag_type = "prev_folder" if is_prev else "folder"
        logger.debug(f"Created {len(tags_to_create)} new {tag_type} tags")
        return new_associations

    def create_folder_tags(
        self,
        articles_path: str,
        max_articles: Optional[int] = None,
        debug: bool = False,
    ) -> None:
        start_time = time.time()
        logger.debug(f"Starting folder tagging at {start_time}")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA synchronous = OFF")
            conn.execute("PRAGMA journal_mode = MEMORY")
            cursor = conn.cursor()
            self._initialize_db(cursor)
            exclusions = self._get_excluded_folders()
            folder_tags, prev_folder_tags = self._fetch_existing_tags(cursor)
            articles = self._get_articles(cursor, max_articles, debug)
            current_article_tags = self._get_current_article_tags(cursor)
            (
                folder_locations,
                tags_to_create,
                prev_tags_to_create,
                article_tag_associations,
                article_prev_tag_associations,
                tags_to_remove,
            ) = self._process_articles(
                articles,
                articles_path,
                exclusions,
                current_article_tags,
                folder_tags,
                prev_folder_tags,
            )
            if tags_to_create:
                new_assoc = self._batch_create_tags(
                    cursor, tags_to_create, folder_tags, folder_locations, False, debug
                )
                article_tag_associations.extend(new_assoc)
            if prev_tags_to_create:
                new_assoc = self._batch_create_tags(
                    cursor,
                    prev_tags_to_create,
                    prev_folder_tags,
                    folder_locations,
                    True,
                    debug,
                )
                article_prev_tag_associations.extend(new_assoc)
            if tags_to_remove:
                cursor.executemany(
                    "DELETE FROM article_tags WHERE article_id = ? AND tag_id = ?",
                    tags_to_remove,
                )
                logger.info(f"Removed {len(tags_to_remove)} folder tag associations")
            if article_tag_associations:
                cursor.executemany(
                    "INSERT OR IGNORE INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, 1)",
                    article_tag_associations,
                )
                logger.info(
                    f"Created {len(article_tag_associations)} new folder tag associations"
                )
            if article_prev_tag_associations:
                cursor.executemany(
                    "INSERT OR IGNORE INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, 1)",
                    article_prev_tag_associations,
                )
                logger.info(
                    f"Created {len(article_prev_tag_associations)} new prev_folder tag associations"
                )
            conn.commit()
        elapsed = time.time() - start_time
        logger.info(f"Folder tagging completed in {elapsed:.2f} seconds")


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
        tags_list: List[Tuple[int, str, str]],
    ) -> Dict[int, bool]:
        if not tags_list or not text:
            return {}
        tag_batches = [
            tags_list[i : i + self.batch_size]
            for i in range(0, len(tags_list), self.batch_size)
        ]
        logger.debug(
            f"Processing {len(tags_list)} tags in {len(tag_batches)} batches (batch size: {self.batch_size})"
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

    def evaluate_if_article_matches_tag(
        self, text: str, tag_name: str, tag_description: str
    ) -> bool:
        try:
            results = self.evaluate_tags(text, [(0, tag_name, tag_description)])
            return results.get(0, False)
        except Exception as e:
            logger.error(
                f"Error evaluating if article matches tag '{tag_name}': {e}\n{traceback.format_exc()}"
            )
            return False


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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            active_tags = {
                tag_name: tag_data
                for tag_name, tag_data in self.config.get("article_tags", {}).items()
                if tag_data.get("enabled", True)
            }
            cursor.execute("SELECT id, name FROM tags")
            return {
                row[0]
                for row in cursor.fetchall()
                if row[1] in active_tags or row[1].startswith("folder_")
            }

    def _get_articles_needing_tagging(self) -> List[Tuple[int, str, str, str]]:
        articles_to_tag = []
        evaluated_count = 0
        seen = set()
        i = 1
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            while evaluated_count < self.max_articles_per_session:
                cursor.execute(
                    """
                    SELECT a.id, a.file_hash, a.file_name, a.summary 
                    FROM article_summaries a
                    WHERE EXISTS (
                        SELECT 1 FROM tags t
                        WHERE t.id NOT IN (
                            SELECT tag_id FROM article_tags WHERE article_id = a.id
                        )
                        AND t.name NOT LIKE 'folder_%'
                        AND t.name NOT LIKE 'prev_folder_%'
                        AND NOT (t.use_summary = 1 AND (a.summary = 'failed_to_extract' OR a.summary = 'failed_to_summarise'))
                    )
                    ORDER BY RANDOM()
                    LIMIT ?
                    """,
                    (self.max_articles_per_session * i,),
                )
                i += 1
                batch = cursor.fetchall()
                batch = [article for article in batch if article[0] not in seen]
                if not batch:
                    break
                for article in batch:
                    seen.add(article[0])
                    work_units = self._prepare_article_work_units(
                        article, self._get_active_tag_ids()
                    )
                    if work_units:
                        articles_to_tag.append(article)
                        evaluated_count += 1
                    if evaluated_count >= self.max_articles_per_session:
                        logger.info(
                            f"Reached max articles to tag: {self.max_articles_per_session}"
                        )
                        break
        return articles_to_tag

    def _get_tags_for_article(
        self, article_id: int, active_tag_ids: Set[int]
    ) -> List[Tuple[int, str, str, bool, List[str], List[str], List[str]]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.id, t.name, t.description, t.use_summary, t.any_tags, t.and_tags, t.not_any_tags
                FROM tags t
                WHERE t.id NOT IN (
                    SELECT tag_id FROM article_tags WHERE article_id = ?
                )
                """,
                (article_id,),
            )
            tags = cursor.fetchall()
        processed = []
        for (
            tag_id,
            tag_name,
            tag_desc,
            use_summary,
            any_tags,
            and_tags,
            not_any_tags,
        ) in tags:
            if (
                not tag_name.startswith("folder_")
                and not tag_name.startswith("prev_")
                and tag_id in active_tag_ids
            ):
                processed.append(
                    (
                        tag_id,
                        tag_name,
                        tag_desc,
                        use_summary,
                        json.loads(any_tags) if any_tags else [],
                        json.loads(and_tags) if and_tags else [],
                        json.loads(not_any_tags) if not_any_tags else [],
                    )
                )
        return processed

    def _get_tag_criteria_cache_key(self, any_tags, and_tags, not_any_tags) -> str:
        return f"any:{'|'.join(sorted(any_tags)) if any_tags else ''}|and:{'|'.join(sorted(and_tags)) if and_tags else ''}|not:{'|'.join(sorted(not_any_tags)) if not_any_tags else ''}"

    def _prepare_article_work_units(
        self, article: Tuple[int, str, str, str], active_tag_ids: Set[int]
    ) -> List[Dict[str, Any]]:
        article_id, file_hash, file_name, summary = article
        tags_to_evaluate = self._get_tags_for_article(article_id, active_tag_ids)
        logger.debug(
            f"Tags to evaluate for article {article_id}: {len(tags_to_evaluate)}"
        )
        if not tags_to_evaluate:
            return []
        filtered_tags = []
        article_path = os.path.join(self.articles_path, file_name)
        for tag in tags_to_evaluate:
            (
                tag_id,
                tag_name,
                tag_desc,
                use_summary,
                any_tags,
                and_tags,
                not_any_tags,
            ) = tag
            if not any_tags and not and_tags and not not_any_tags:
                filtered_tags.append((tag_id, tag_name, tag_desc, use_summary))
            else:
                cache_key = self._get_tag_criteria_cache_key(
                    any_tags, and_tags, not_any_tags
                )
                if cache_key in self.tag_search_cache:
                    if article_id in self.tag_search_cache[cache_key]:
                        filtered_tags.append((tag_id, tag_name, tag_desc, use_summary))
                    else:
                        logger.debug(
                            f"Article {article_id} filtered out for tag {tag_name} (cache hit)"
                        )
                else:
                    logger.debug(
                        f"No cache entry for {cache_key}, including tag {tag_name} without filtering"
                    )
                    filtered_tags.append((tag_id, tag_name, tag_desc, use_summary))
        if not filtered_tags:
            logger.debug(
                f"No tags to evaluate for article {article_id} after filtering"
            )
            return []
        summary_tags = []
        full_text_tags = []
        for tag_id, tag_name, tag_desc, use_summary in filtered_tags:
            if use_summary:
                if summary and summary not in [
                    "failed_to_extract",
                    "failed_to_summarise",
                ]:
                    summary_tags.append((tag_id, tag_name, tag_desc))
            else:
                full_text_tags.append((tag_id, tag_name, tag_desc))
        work_units = []
        if summary_tags:
            work_units.append(
                {
                    "article_id": article_id,
                    "file_hash": file_hash,
                    "file_name": file_name,
                    "text": summary,
                    "tags": summary_tags,
                    "use_summary": True,
                }
            )
        if full_text_tags:
            work_units.append(
                {
                    "article_id": article_id,
                    "file_hash": file_hash,
                    "file_name": file_name,
                    "text": None,
                    "tags": full_text_tags,
                    "use_summary": False,
                }
            )
        return work_units

    def _process_article_tag_batch(
        self,
        article_id: int,
        file_name: str,
        text: str,
        tags_batch: List[Tuple[int, str, str]],
    ) -> Dict:
        results = {"matches": [], "non_matches": []}
        if not text:
            logger.warning(f"Empty text for article {article_id}, file: {file_name}")
            return results
        for tag_id, tag_name, tag_desc in tags_batch:
            try:
                if self.tag_evaluator.evaluate_if_article_matches_tag(
                    text, tag_name, tag_desc
                ):
                    results["matches"].append((tag_id, tag_name, tag_desc))
                else:
                    results["non_matches"].append((tag_id, tag_name, tag_desc))
            except Exception as e:
                logger.error(
                    f"Error evaluating tag {tag_name} for article {article_id}: {e}"
                )
                results["non_matches"].append((tag_id, tag_name, tag_desc))
        return results

    def _process_work_units(self, work_units: List[Dict]) -> Dict[int, Dict]:
        if not work_units:
            logger.debug("No work units to process")
            return {}
        logger.info(f"Processing {len(work_units)} work units in parallel")
        results_by_article = {}
        file_names = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_tagging_threads
        ) as executor:
            futures = {}
            for unit in work_units:
                article_id = unit["article_id"]
                file_name = unit["file_name"]
                file_names[article_id] = file_name
                text = unit["text"]
                if not unit["use_summary"] and text is None:
                    file_path = os.path.join(self.articles_path, file_name)
                    if os.path.exists(file_path):
                        try:
                            text = extract_text_from_file(file_path, self.config)
                        except Exception as e:
                            logger.error(f"Error extracting text from {file_name}: {e}")
                            continue
                    else:
                        logger.warning(f"File not found: {file_path}")
                        continue
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
                            "file_name": file_names[article_id],
                            "matches": [],
                            "non_matches": [],
                        }
                    results_by_article[article_id]["matches"].extend(
                        batch_results["matches"]
                    )
                    results_by_article[article_id]["non_matches"].extend(
                        batch_results["non_matches"]
                    )
                except Exception as e:
                    logger.error(
                        f"Error processing article {article_id}: {e}\n{traceback.format_exc()}"
                    )
        return results_by_article

    def _apply_tag_results_to_articles(
        self, results_by_article: Dict[int, Dict]
    ) -> None:
        logger.info(f"Applying results to {len(results_by_article)} articles")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")
            try:
                for article_id, result in results_by_article.items():
                    for tag in result["matches"]:
                        tag_id, tag_name, tag_desc = tag
                        cursor.execute(
                            "SELECT 1 FROM article_tags WHERE article_id = ? AND tag_id = ?",
                            (article_id, tag_id),
                        )
                        if cursor.fetchone():
                            cursor.execute(
                                "UPDATE article_tags SET matches = 1 WHERE article_id = ? AND tag_id = ?",
                                (article_id, tag_id),
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, 1)",
                                (article_id, tag_id),
                            )
                    for tag in result["non_matches"]:
                        tag_id, tag_name, tag_desc = tag
                        cursor.execute(
                            "SELECT 1 FROM article_tags WHERE article_id = ? AND tag_id = ?",
                            (article_id, tag_id),
                        )
                        if cursor.fetchone():
                            cursor.execute(
                                "UPDATE article_tags SET matches = 0 WHERE article_id = ? AND tag_id = ?",
                                (article_id, tag_id),
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, 0)",
                                (article_id, tag_id),
                            )
                conn.commit()
                logger.info(
                    f"Successfully applied tag results to {len(results_by_article)} articles"
                )
            except Exception as e:
                conn.rollback()
                logger.error(
                    f"Error applying tag results to articles: {e}\n{traceback.format_exc()}"
                )

    def _cache_tag_search_results(self, cursor: sqlite3.Cursor) -> None:
        try:
            cursor.execute(
                "SELECT id, name, any_tags, and_tags, not_any_tags FROM tags"
            )
            all_tags = cursor.fetchall()
            self.tag_search_cache = {}
            for (
                tag_id,
                tag_name,
                any_tags_json,
                and_tags_json,
                not_any_tags_json,
            ) in all_tags:
                any_tags = json.loads(any_tags_json) if any_tags_json else []
                and_tags = json.loads(and_tags_json) if and_tags_json else []
                not_any_tags = (
                    json.loads(not_any_tags_json) if not_any_tags_json else []
                )
                if not any_tags and not and_tags and not not_any_tags:
                    continue
                cache_key = self._get_tag_criteria_cache_key(
                    any_tags, and_tags, not_any_tags
                )
                if cache_key not in self.tag_search_cache:
                    matching_articles = searchArticlesByTags(
                        all_tags=and_tags,
                        any_tags=any_tags,
                        not_any_tags=not_any_tags,
                        cursor=cursor,
                    )
                    self.tag_search_cache[cache_key] = set(matching_articles.keys())
                    logger.debug(
                        f"Cached {len(matching_articles)} articles for criteria: {cache_key}"
                    )
        except Exception as e:
            logger.error(
                f"Error caching tag search results: {e}\n{traceback.format_exc()}"
            )

    def apply_tags_to_articles(self) -> None:
        active_tag_ids = self._get_active_tag_ids()
        articles_to_tag = self._get_articles_needing_tagging()
        if len(articles_to_tag) > self.max_articles_per_session:
            articles_to_tag = articles_to_tag[: self.max_articles_per_session]
        logger.info(f"Found {len(articles_to_tag)} articles that need tagging")
        if not articles_to_tag:
            logger.info("No articles to tag")
            return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            self._cache_tag_search_results(cursor)
            all_work_units = []
            for article in articles_to_tag:
                all_work_units.extend(
                    self._prepare_article_work_units(article, active_tag_ids)
                )
            logger.info(
                f"Created {len(all_work_units)} work units for parallel processing"
            )
            results = self._process_work_units(all_work_units)
            self._apply_tag_results_to_articles(results)


def analyze_tag_results(tag_name: str) -> None:
    """Analyze which articles match or do not match a specific tag and output a markdown report."""
    logger.info(f"Analyzing results for tag: {tag_name}")
    db_path = setup_tag_database()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_result = cursor.fetchone()
        if not tag_result:
            logger.error(f"Tag '{tag_name}' not found in the database")
            return
        tag_id = tag_result[0]
        cursor.execute(
            """
            SELECT a.file_name 
            FROM article_summaries a
            JOIN article_tags t ON a.id = t.article_id
            WHERE t.tag_id = ? AND t.matches = 1
            ORDER BY a.file_name
            """,
            (tag_id,),
        )
        matching_articles = [row[0] for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT a.file_name 
            FROM article_summaries a
            JOIN article_tags t ON a.id = t.article_id
            WHERE t.tag_id = ? AND t.matches = 0
            ORDER BY a.file_name
            """,
            (tag_id,),
        )
        non_matching_articles = [row[0] for row in cursor.fetchall()]
    markdown_content = f"# Tag Analysis: {tag_name}\n\nGenerated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    markdown_content += f"## Articles Matching Tag ({len(matching_articles)})\n\n"
    markdown_content += (
        "\n".join(f"- {a}" for a in matching_articles)
        if matching_articles
        else "No articles match this tag.\n"
    )
    markdown_content += (
        f"\n## Articles Not Matching Tag ({len(non_matching_articles)})\n\n"
    )
    markdown_content += (
        "\n".join(f"- {a}" for a in non_matching_articles)
        if non_matching_articles
        else "No articles have been explicitly categorized as not matching this tag.\n"
    )
    output_path = PROJECT_ROOT / "TAG_ANALYSE.md"
    with open(output_path, "w") as f:
        f.write(markdown_content)
    logger.info(f"Tag analysis saved to {output_path}")
    print(f"Tag analysis completed. Results saved to {output_path}")


def main():
    """Main entry point for the tagging process."""
    load_environment_variables()
    parser = argparse.ArgumentParser(description="Apply tags to articles")
    parser.add_argument(
        "--folder-tags-only",
        action="store_true",
        help="Only create folder tags without applying other tags",
    )
    parser.add_argument(
        "--analyze-tag",
        type=str,
        help="Analyze a specific tag and save results to TAG_ANALYSE.md",
    )
    args = parser.parse_args()
    try:
        db_path = setup_tag_database()
        config = getConfig()
        articles_path = config.get("articleFileFolder", "")
        if not articles_path:
            logger.error("Error: articleFileFolder not specified in config.json")
            return
        logger.info("Creating folder tags...")
        tag_manager = TagManager(db_path)
        tag_manager.sync_tags_from_config()
        tag_manager.create_folder_tags(articles_path)
        if not args.folder_tags_only:
            logger.info("Applying tags to articles...")
            ArticleTagger(db_path).apply_tags_to_articles()
        else:
            logger.info("Skipping AI-based tagging (folder-tags-only mode)")
        if args.analyze_tag:
            analyze_tag_results(args.analyze_tag)
        logger.info("Tagging process completed successfully")
    except Exception as e:
        logger.error(f"An error occurred: {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
