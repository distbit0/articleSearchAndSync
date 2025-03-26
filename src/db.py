import sqlite3
import os
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set, Optional
from loguru import logger
from . import utils

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
DB_FILENAME = "article_summaries.db"
DB_PATH = STORAGE_DIR / DB_FILENAME


def get_db_path() -> str:
    STORAGE_DIR.mkdir(exist_ok=True)
    return str(DB_PATH)


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(get_db_path())


def setup_database() -> str:
    db_path = get_db_path()
    with get_connection() as conn:
        conn.executescript(
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
            );
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
    return db_path


# Article Summary Operations


def get_article_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, file_hash, file_name, file_format, summary, extraction_method, word_count, created_at FROM article_summaries WHERE file_hash = ?",
            (file_hash,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "file_hash": row[1],
        "file_name": row[2],
        "file_format": row[3],
        "summary": row[4],
        "extraction_method": row[5],
        "word_count": row[6],
        "created_at": row[7],
    }


def get_article_by_file_name(file_name: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, file_hash, file_name, file_format, summary, extraction_method, word_count, created_at FROM article_summaries WHERE file_name = ?",
            (file_name,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "file_hash": row[1],
        "file_name": row[2],
        "file_format": row[3],
        "summary": row[4],
        "extraction_method": row[5],
        "word_count": row[6],
        "created_at": row[7],
    }


def update_article_summary(
    file_hash: str,
    file_name: str,
    file_format: str,
    summary: str,
    extraction_method: str,
    word_count: int,
) -> int:
    with get_connection() as conn:
        article_id = get_article_by_hash(file_hash)["id"]
        if article_id:
            conn.execute(
                """
                UPDATE article_summaries
                SET file_name = ?, file_format = ?, summary = ?, extraction_method = ?, word_count = ?
                WHERE id = ?
                """,
                (
                    file_name,
                    file_format,
                    summary,
                    extraction_method,
                    word_count,
                    article_id,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO article_summaries (file_hash, file_name, file_format, summary, extraction_method, word_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    file_hash,
                    file_name,
                    file_format,
                    summary,
                    extraction_method,
                    word_count,
                ),
            )
            article_id = cursor.lastrowid
        conn.commit()
    return article_id


def add_file_to_database(
    file_hash: str,
    file_name: str,
    file_format: str,
    summary: Optional[str] = None,
    extraction_method: Optional[str] = None,
    word_count: int = 0,
) -> int:
    with get_connection() as conn:
        existing_id = get_article_by_hash(file_hash)["id"]
        if existing_id:
            return existing_id
        cursor = conn.execute(
            """
            INSERT INTO article_summaries (file_hash, file_name, file_format, summary, extraction_method, word_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_hash, file_name, file_format, summary, extraction_method, word_count),
        )
        article_id = cursor.lastrowid
        conn.commit()
    return article_id


def get_all_file_hashes() -> List[str]:
    with get_connection() as conn:
        cursor = conn.execute("SELECT file_hash FROM article_summaries")
        return [row[0] for row in cursor.fetchall()]


def get_articles_needing_summary() -> List[Tuple[str, str]]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT file_hash, file_name FROM article_summaries WHERE summary IS NULL OR summary = ''"
        )
        return cursor.fetchall()


def remove_nonexistent_files(existing_files: Set[str]) -> int:
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, file_name FROM article_summaries")
        files_to_remove = [
            file_id
            for file_id, file_name in cursor.fetchall()
            if file_name not in existing_files
        ]
        if files_to_remove:
            for file_id in files_to_remove:
                conn.execute(
                    "DELETE FROM article_tags WHERE article_id = ?", (file_id,)
                )
            placeholders = ",".join("?" for _ in files_to_remove)
            conn.execute(
                f"DELETE FROM article_summaries WHERE id IN ({placeholders})",
                files_to_remove,
            )
            conn.commit()
        return len(files_to_remove)


# Tag Operations


def get_tag_property_hash(
    description: str,
    use_summary: bool,
    any_tags: List[str] = None,
    and_tags: List[str] = None,
    not_any_tags: List[str] = None,
) -> str:
    any_tags = any_tags or []
    and_tags = and_tags or []
    not_any_tags = not_any_tags or []
    property_string = f"{description}|{use_summary}|{'|'.join(sorted(any_tags))}|{'|'.join(sorted(and_tags))}|{'|'.join(sorted(not_any_tags))}"
    return hashlib.md5(property_string.encode()).hexdigest()


def sync_tags_from_config(config: Dict[str, Any]) -> None:
    tag_config = config.get("article_tags", {})
    if not tag_config:
        logger.error("No 'article_tags' section found in config.json")
        return

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tags)")
        columns = {row[1] for row in cursor.fetchall()}
        for col in ("any_tags", "and_tags", "not_any_tags"):
            if col not in columns:
                cursor.execute(f"ALTER TABLE tags ADD COLUMN {col} TEXT")

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

        cursor.execute("SELECT tag_id, property_hash FROM tag_hashes")
        property_hashes = {row[0]: row[1] for row in cursor.fetchall()}

        config_tag_names = {
            tag_name
            for tag_name, tag_data in tag_config.items()
            if not isinstance(tag_data, list)
        }

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
                        """
                        UPDATE tags SET description = ?, use_summary = ?, any_tags = ?, and_tags = ?, not_any_tags = ?, last_updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
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
                    """
                    INSERT INTO tags (name, description, use_summary, any_tags, and_tags, not_any_tags)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
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

        for tag_name in set(existing_tags) - config_tag_names:
            tag_id = existing_tags[tag_name]["id"]
            cursor.execute("DELETE FROM article_tags WHERE tag_id = ?", (tag_id,))
            cursor.execute("DELETE FROM tag_hashes WHERE tag_id = ?", (tag_id,))
            cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            logger.debug(f"Deleted tag '{tag_name}' as it no longer exists in config")

        conn.commit()


def get_tag_id_by_name(tag_name: str) -> Optional[int]:
    with get_connection() as conn:
        cursor = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        row = cursor.fetchone()
    return row[0] if row else None


def get_all_tags() -> List[Tuple[int, str]]:
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, name FROM tags")
        return cursor.fetchall()


def get_tags_for_article(article_id: int) -> List[int]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT tag_id FROM article_tags WHERE article_id = ?", (article_id,)
        )
        return [row[0] for row in cursor.fetchall()]


def get_all_tag_details() -> Dict[int, Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, description, use_summary, any_tags, and_tags, not_any_tags FROM tags"
        )
        return {
            row[0]: {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "use_summary": bool(row[3]),
                "any_tags": json.loads(row[4]) if row[4] else [],
                "and_tags": json.loads(row[5]) if row[5] else [],
                "not_any_tags": json.loads(row[6]) if row[6] else [],
            }
            for row in cursor.fetchall()
        }


def set_article_tag(article_id: int, tag_id: int, matches: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, ?)",
            (article_id, tag_id, 1 if matches else 0),
        )
        conn.commit()


def remove_orphaned_tags() -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM article_tags)"
        )
        conn.commit()
    return cursor.rowcount


# Search Operations


def get_articles_by_tag(tag_name: str) -> List[str]:
    tag_id = get_tag_id_by_name(tag_name)
    if not tag_id:
        return []
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT a.file_name FROM article_summaries a JOIN article_tags at ON a.id = at.article_id WHERE at.tag_id = ? AND at.matches = 1",
            (tag_id,),
        )
        return [row[0] for row in cursor.fetchall()]


def get_articles_not_matching_tag(tag_name: str) -> List[str]:
    tag_id = get_tag_id_by_name(tag_name)
    if not tag_id:
        return []
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT a.file_name FROM article_summaries a JOIN article_tags at ON a.id = at.article_id WHERE at.tag_id = ? AND at.matches = 0",
            (tag_id,),
        )
        return [row[0] for row in cursor.fetchall()]


def get_articles_needing_tagging(
    max_articles: Optional[int] = None,
) -> List[Tuple[int, str, str, str]]:
    query = """
        SELECT a.id, a.file_hash, a.file_name, a.summary 
        FROM article_summaries a
        WHERE NOT EXISTS (SELECT 1 FROM article_tags WHERE article_id = a.id)
        AND a.summary IS NOT NULL AND a.summary != ''
        ORDER BY RANDOM()
    """
    if max_articles:
        query += f" LIMIT {max_articles}"
    with get_connection() as conn:
        cursor = conn.execute(query)
        return cursor.fetchall()


def get_all_tags_with_article_count() -> List[Tuple[int, str, int]]:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT t.id, t.name, COUNT(at.article_id) 
            FROM tags t LEFT JOIN article_tags at ON t.id = at.tag_id AND at.matches = 1 
            GROUP BY t.id, t.name
            """
        )
        return cursor.fetchall()


def get_articles_for_tag(tag_id: int) -> List[Tuple[int, str]]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT a.id, a.file_name FROM article_summaries a JOIN article_tags at ON a.id = at.article_id WHERE at.tag_id = ? AND at.matches = 1",
            (tag_id,),
        )
        return cursor.fetchall()


def clean_orphaned_database_items() -> Tuple[int, int]:
    orphaned_tags = remove_orphaned_tags()
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM tag_hashes WHERE tag_id NOT IN (SELECT id FROM tags)"
        )
        conn.commit()
    orphaned_hashes = cursor.rowcount
    return orphaned_tags, orphaned_hashes


def searchArticlesByTags(
    all_tags=[], any_tags=[], not_any_tags=[], readState="", formats=[]
):
    """
    Search for articles that match specified tags.

    Args:
        all_tags: List of tags where all must match (AND logic)
        any_tags: List of tags where any must match (OR logic)
        not_any_tags: List of tags where none should match (NOT ANY logic)
        readState: Filter by read state ('read', 'unread', or '') - empty string means no filtering
        formats: List of file formats to include
        path: Base path to search in

    Returns:
        Dict of article paths with their URLs
    """
    # Early return conditions
    is_format_specific = (
        formats
        and len(formats) > 0
        and formats != utils.getConfig()["docFormatsToMove"]
    )
    if not all_tags and not any_tags and not not_any_tags and not is_format_specific:
        return {}

    # Get database path
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "storage",
        "article_summaries.db",
    )
    if not os.path.exists(db_path):
        print(f"Tag database not found at {db_path}")
        return {}

    # Get all article paths that match the format criteria
    article_paths = utils.getArticlePathsForQuery("*", formats, readState=readState)

    # If no tags specified and only filtering by format, just apply read state filter and return
    if not all_tags and not any_tags and not not_any_tags:
        matchingArticles = {
            articlePath: utils.getUrlOfArticle(articlePath)
            for articlePath in article_paths
        }
        return matchingArticles

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Extract filenames from paths for efficient filtering
        filenames = {os.path.basename(path): path for path in article_paths}

        # Build SQL query for tag filtering
        query_params = []

        # Base SQL query to get article summaries
        sql = """
        SELECT as1.file_name, as1.id 
        FROM article_summaries as1
        WHERE as1.file_name IN ({})
        """.format(
            ",".join(["?"] * len(filenames))
        )

        query_params.extend(filenames.keys())

        # Filter by all_tags (AND logic)
        if all_tags:
            # For each required tag, join to article_tags and check for match
            for i, tag in enumerate(all_tags):
                tag_alias = f"at{i}"
                tag_join = f"""
                JOIN article_tags {tag_alias} ON as1.id = {tag_alias}.article_id
                JOIN tags t{i} ON {tag_alias}.tag_id = t{i}.id AND t{i}.name = ? AND {tag_alias}.matches = 1
                """
                sql = sql.replace(
                    "FROM article_summaries as1",
                    f"FROM article_summaries as1 {tag_join}",
                )
                query_params.append(tag)

        # Filter by any_tags (OR logic)
        if any_tags:
            or_conditions = []
            for tag in any_tags:
                or_conditions.append("(t_any.name = ? AND at_any.matches = 1)")
                query_params.append(tag)

            if or_conditions:
                any_tag_join = """
                JOIN article_tags at_any ON as1.id = at_any.article_id
                JOIN tags t_any ON at_any.tag_id = t_any.id
                """
                any_tag_where = " AND (" + " OR ".join(or_conditions) + ")"

                # Add the join to the FROM clause
                sql = sql.replace(
                    "FROM article_summaries as1",
                    f"FROM article_summaries as1 {any_tag_join}",
                )
                # Add the OR conditions to the WHERE clause
                sql += any_tag_where

        # Filter by not_any_tags (NOT ANY logic)
        if not_any_tags:
            # Create a subquery to exclude articles that have any of the excluded tags
            not_any_subquery = """
            NOT EXISTS (
                SELECT 1 
                FROM article_tags at_not 
                JOIN tags t_not ON at_not.tag_id = t_not.id 
                WHERE as1.id = at_not.article_id 
                AND at_not.matches = 1 
                AND t_not.name IN ({})
            )
            """.format(
                ",".join(["?"] * len(not_any_tags))
            )

            query_params.extend(not_any_tags)
            sql += " AND " + not_any_subquery

        # Execute query
        cursor.execute(sql, query_params)
        matching_files = cursor.fetchall()

        # Build result dictionary
        matchingArticles = {
            filenames[filename]: utils.getUrlOfArticle(filenames[filename])
            for filename, _ in matching_files
            if filename in filenames
        }
        return matchingArticles

    finally:
        if cursor:
            cursor.connection.close()
