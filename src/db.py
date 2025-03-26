import sqlite3
import json
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set, Optional, Union, Iterable
from loguru import logger


# Constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = PROJECT_ROOT / "storage"
DB_FILENAME = "article_summaries.db"
DB_PATH = STORAGE_DIR / DB_FILENAME


def get_db_path() -> str:
    """Get the path to the SQLite database file.

    Returns:
        str: Absolute path to the database file
    """
    STORAGE_DIR.mkdir(exist_ok=True)
    return str(DB_PATH)


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database.

    Returns:
        sqlite3.Connection: SQLite database connection
    """
    return sqlite3.connect(get_db_path())


def setup_database() -> str:
    """Setup the SQLite database and create necessary tables.

    Returns:
        str: Path to the database file
    """
    db_path = get_db_path()

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executescript(
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
        conn.commit()

    return db_path


# Article Summary Operations


def get_article_summary_by_hash(file_hash: str) -> Optional[str]:
    """Get article summary by file hash.

    Args:
        file_hash: Hash of the file

    Returns:
        Optional[str]: Summary text if found, None otherwise
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT summary FROM article_summaries WHERE file_hash = ?", (file_hash,)
        )
        result = cursor.fetchone()
        return result[0] if result else None


def get_article_id_by_hash(file_hash: str) -> Optional[int]:
    """Get article ID by file hash.

    Args:
        file_hash: Hash of the file

    Returns:
        Optional[int]: Article ID if found, None otherwise
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM article_summaries WHERE file_hash = ?", (file_hash,)
        )
        result = cursor.fetchone()
        return result[0] if result else None


def get_article_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    """Get full article details by file hash.

    Args:
        file_hash: Hash of the file

    Returns:
        Optional[Dict[str, Any]]: Article details if found, None otherwise
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, file_hash, file_name, file_format, summary, extraction_method, word_count, created_at 
            FROM article_summaries 
            WHERE file_hash = ?
            """,
            (file_hash,),
        )
        result = cursor.fetchone()

        if not result:
            return None

        return {
            "id": result[0],
            "file_hash": result[1],
            "file_name": result[2],
            "file_format": result[3],
            "summary": result[4],
            "extraction_method": result[5],
            "word_count": result[6],
            "created_at": result[7],
        }


def update_article_summary(
    file_hash: str,
    file_name: str,
    file_format: str,
    summary: str,
    extraction_method: str,
    word_count: int,
) -> int:
    """Update or insert article summary.

    Args:
        file_hash: Hash of the file
        file_name: Name of the file
        file_format: Format of the file
        summary: Summary text
        extraction_method: Method used to extract text
        word_count: Word count of the article

    Returns:
        int: Article ID
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check if article already exists
        cursor.execute(
            "SELECT id FROM article_summaries WHERE file_hash = ?", (file_hash,)
        )
        result = cursor.fetchone()

        if result:
            # Update existing article
            article_id = result[0]
            cursor.execute(
                """
                UPDATE article_summaries
                SET file_name = ?, file_format = ?, summary = ?, 
                    extraction_method = ?, word_count = ?
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
            # Insert new article
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
) -> int | None:
    """Add a file to the database with optional summary information.

    Args:
        file_hash: Hash of the file
        file_name: Name of the file
        file_format: Format of the file
        summary: Optional summary text
        extraction_method: Optional text extraction method
        word_count: Word count (default 0)

    Returns:
        int: Article ID
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check if article already exists
        cursor.execute(
            "SELECT id FROM article_summaries WHERE file_hash = ?", (file_hash,)
        )
        result = cursor.fetchone()

        if result:
            # Article already exists, return its ID
            return result[0]

        # Insert new article
        cursor.execute(
            """
            INSERT INTO article_summaries 
            (file_hash, file_name, file_format, summary, extraction_method, word_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_hash, file_name, file_format, summary, extraction_method, word_count),
        )
        article_id = cursor.lastrowid
        conn.commit()

        return article_id


def get_all_file_hashes() -> List[str]:
    """Get all file hashes from the database.

    Returns:
        List[str]: List of file hashes
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_hash FROM article_summaries")
        return [row[0] for row in cursor.fetchall()]


def get_all_articles() -> List[Tuple[int, str]]:
    """Get all articles (ID and filename) from the database.

    Returns:
        List[Tuple[int, str]]: List of tuples containing article ID and filename
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, file_name FROM article_summaries")
        return cursor.fetchall()


def get_articles_needing_summary() -> List[Tuple[str, str]]:
    """Get articles that need summarization (NULL or empty summary).

    Returns:
        List[Tuple[str, str]]: List of tuples containing file_hash and file_name
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT file_hash, file_name
            FROM article_summaries
            WHERE summary IS NULL OR summary = ''
            """
        )
        return cursor.fetchall()


def remove_article_by_id(article_id: int) -> None:
    """Remove an article and its tag associations by ID.

    Args:
        article_id: ID of the article to remove
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # First remove tag associations
        cursor.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
        # Then remove the article
        cursor.execute("DELETE FROM article_summaries WHERE id = ?", (article_id,))
        conn.commit()


def remove_article_by_hash(file_hash: str) -> bool:
    """Remove an article and its tag associations by file hash.

    Args:
        file_hash: Hash of the file

    Returns:
        bool: True if an article was removed, False otherwise
    """
    article_id = get_article_id_by_hash(file_hash)
    if article_id:
        remove_article_by_id(article_id)
        return True
    return False


def get_articles_by_filename(filenames: List[str]) -> Dict[str, int]:
    """Get article IDs by filenames.

    Args:
        filenames: List of filenames to look up

    Returns:
        Dict[str, int]: Dictionary mapping filenames to article IDs
    """
    if not filenames:
        return {}

    # Prepare placeholders for SQL query
    placeholders = ",".join(["?"] * len(filenames))

    with get_connection() as conn:
        cursor = conn.cursor()
        query = f"""
            SELECT file_name, id
            FROM article_summaries
            WHERE file_name IN ({placeholders})
        """
        cursor.execute(query, filenames)

        # Convert results to dictionary
        return {row[0]: row[1] for row in cursor.fetchall()}


def remove_nonexistent_files(existing_files: Set[str]) -> int:
    """Remove database entries for files that no longer exist.

    Args:
        existing_files: Set of filenames that still exist

    Returns:
        int: Number of files removed from the database
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Get all file entries from the database
        cursor.execute("SELECT id, file_name FROM article_summaries")
        db_files = cursor.fetchall()

        # Find files in database that don't exist on filesystem
        removed_count = 0
        files_to_remove = []

        for file_id, file_name in db_files:
            if file_name not in existing_files:
                files_to_remove.append(file_id)

        # Remove files in batches
        if files_to_remove:
            # First, remove entries from article_tags
            for file_id in files_to_remove:
                cursor.execute(
                    "DELETE FROM article_tags WHERE article_id = ?", (file_id,)
                )

            # Then remove from article_summaries
            placeholder = ",".join(["?"] * len(files_to_remove))
            cursor.execute(
                f"DELETE FROM article_summaries WHERE id IN ({placeholder})",
                files_to_remove,
            )
            removed_count = len(files_to_remove)

        conn.commit()
        return removed_count


# Tag Operations


def get_tag_property_hash(
    description: str,
    use_summary: bool,
    any_tags: List[str] = [],
    and_tags: List[str] = [],
    not_any_tags: List[str] = [],
) -> str:
    """Compute an MD5 hash from tag properties.

    Args:
        description: Tag description
        use_summary: Whether to use article summary for tagging
        any_tags: List of tags where any must match
        and_tags: List of tags where all must match
        not_any_tags: List of tags where none should match

    Returns:
        str: MD5 hash string
    """
    any_tags_str = "|".join(sorted(any_tags or []))
    and_tags_str = "|".join(sorted(and_tags or []))
    not_any_tags_str = "|".join(sorted(not_any_tags or []))
    property_string = (
        f"{description}|{use_summary}|{any_tags_str}|{and_tags_str}|{not_any_tags_str}"
    )
    return hashlib.md5(property_string.encode()).hexdigest()


def sync_tags_from_config(config: Dict[str, Any]) -> None:
    """Synchronize tag definitions from config into the database.

    Args:
        config: Config dictionary containing tag definitions
    """
    tag_config = config.get("article_tags", {})
    if not tag_config:
        logger.error("No 'article_tags' section found in config.json")
        return

    with get_connection() as conn:
        cursor = conn.cursor()

        # Ensure filtering columns exist
        cursor.execute("PRAGMA table_info(tags)")
        columns = {row[1] for row in cursor.fetchall()}
        for col in ("any_tags", "and_tags", "not_any_tags"):
            if col not in columns:
                cursor.execute(f"ALTER TABLE tags ADD COLUMN {col} TEXT")

        # Load existing tags
        cursor.execute(
            """SELECT id, name, description, use_summary, any_tags, and_tags, not_any_tags 
               FROM tags"""
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

        # Get set of tag names from config, excluding list-type entries
        config_tag_names = {
            tag_name
            for tag_name, tag_data in tag_config.items()
            if not isinstance(tag_data, list)
        }

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
                        """UPDATE tags SET description = ?, use_summary = ?, any_tags = ?, 
                           and_tags = ?, not_any_tags = ?, last_updated = CURRENT_TIMESTAMP 
                           WHERE id = ?""",
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
                    """INSERT INTO tags (name, description, use_summary, any_tags, and_tags, 
                       not_any_tags) VALUES (?, ?, ?, ?, ?, ?)""",
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

        # Delete tags that are no longer in the config
        tags_to_delete = set(existing_tags.keys()) - config_tag_names

        for tag_name in tags_to_delete:
            tag_id = existing_tags[tag_name]["id"]

            # First delete from article_tags to maintain referential integrity
            cursor.execute("DELETE FROM article_tags WHERE tag_id = ?", (tag_id,))

            # Then delete from tag_hashes
            cursor.execute("DELETE FROM tag_hashes WHERE tag_id = ?", (tag_id,))

            # Finally delete the tag itself
            cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))

            logger.debug(f"Deleted tag '{tag_name}' as it no longer exists in config")

        conn.commit()


def get_tag_id_by_name(tag_name: str) -> Optional[int]:
    """Get tag ID by name.

    Args:
        tag_name: Name of the tag

    Returns:
        Optional[int]: Tag ID if found, None otherwise
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        result = cursor.fetchone()
        return result[0] if result else None


def get_all_tags() -> List[Tuple[int, str]]:
    """Get all tags (ID and name) from the database.

    Returns:
        List[Tuple[int, str]]: List of tuples containing tag ID and name
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM tags")
        return cursor.fetchall()


def get_tags_for_article(article_id: int) -> List[int]:
    """Get all tag IDs for an article.

    Args:
        article_id: ID of the article

    Returns:
        List[int]: List of tag IDs associated with the article
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tag_id FROM article_tags WHERE article_id = ?", (article_id,)
        )
        return [row[0] for row in cursor.fetchall()]


def get_tag_details(tag_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed information about a tag.

    Args:
        tag_id: ID of the tag

    Returns:
        Optional[Dict[str, Any]]: Tag details if found, None otherwise
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, name, description, use_summary, any_tags, and_tags, not_any_tags
               FROM tags WHERE id = ?""",
            (tag_id,),
        )
        result = cursor.fetchone()

        if not result:
            return None

        return {
            "id": result[0],
            "name": result[1],
            "description": result[2],
            "use_summary": bool(result[3]),
            "any_tags": json.loads(result[4]) if result[4] else [],
            "and_tags": json.loads(result[5]) if result[5] else [],
            "not_any_tags": json.loads(result[6]) if result[6] else [],
        }


def get_all_tag_details() -> Dict[int, Dict[str, Any]]:
    """Get detailed information about all tags.

    Returns:
        Dict[int, Dict[str, Any]]: Dictionary mapping tag IDs to tag details
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, name, description, use_summary, any_tags, and_tags, not_any_tags
               FROM tags"""
        )
        results = cursor.fetchall()

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
            for row in results
        }


def set_article_tag(article_id: int, tag_id: int, matches: bool) -> None:
    """Set or update an article-tag relationship.

    Args:
        article_id: ID of the article
        tag_id: ID of the tag
        matches: Whether the article matches the tag
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check if relationship already exists
        cursor.execute(
            "SELECT 1 FROM article_tags WHERE article_id = ? AND tag_id = ?",
            (article_id, tag_id),
        )

        if cursor.fetchone():
            # Update existing relationship
            cursor.execute(
                "UPDATE article_tags SET matches = ? WHERE article_id = ? AND tag_id = ?",
                (1 if matches else 0, article_id, tag_id),
            )
        else:
            # Insert new relationship
            cursor.execute(
                "INSERT INTO article_tags (article_id, tag_id, matches) VALUES (?, ?, ?)",
                (article_id, tag_id, 1 if matches else 0),
            )

        conn.commit()


def remove_article_tag(article_id: int, tag_id: int) -> None:
    """Remove an article-tag relationship.

    Args:
        article_id: ID of the article
        tag_id: ID of the tag
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM article_tags WHERE article_id = ? AND tag_id = ?",
            (article_id, tag_id),
        )
        conn.commit()


def get_current_article_tags() -> Dict[int, Dict[str, List[Tuple[int, str]]]]:
    """Get all current article-tag relationships.

    Returns:
        Dict[int, Dict[str, List[Tuple[int, str]]]]: Dictionary mapping article IDs to
        dictionaries with 'matching' and 'not_matching' lists of tag tuples (tag_id, tag_name)
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT at.article_id, t.name, t.id, at.matches 
               FROM article_tags at
               JOIN tags t ON at.tag_id = t.id"""
        )

        result = {}
        for article_id, tag_name, tag_id, matches in cursor.fetchall():
            if article_id not in result:
                result[article_id] = {"matching": [], "not_matching": []}

            if matches:
                result[article_id]["matching"].append((tag_id, tag_name))
            else:
                result[article_id]["not_matching"].append((tag_id, tag_name))

        return result


def remove_orphaned_tags() -> int:
    """Remove tags from the database that don't have any associated articles.

    Returns:
        int: Number of orphaned tags removed
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """DELETE FROM tags 
               WHERE id NOT IN (
                   SELECT DISTINCT tag_id FROM article_tags
               )"""
        )
        removed_count = cursor.rowcount
        conn.commit()
        return removed_count


# Search Operations


def search_articles_by_tags(
    all_tags: List[str] = None,
    any_tags: List[str] = None,
    not_any_tags: List[str] = None,
    filenames: List[str] = None,
) -> List[Tuple[str, int]]:
    """Search for articles that match specified tag criteria.

    Args:
        all_tags: List of tags where all must match (AND logic)
        any_tags: List of tags where any must match (OR logic)
        not_any_tags: List of tags where none should match (NOT ANY logic)
        filenames: Optional list of filenames to filter by

    Returns:
        List[Tuple[str, int]]: List of tuples containing article filename and ID
    """
    all_tags = all_tags or []
    any_tags = any_tags or []
    not_any_tags = not_any_tags or []

    # If no tags specified, return empty list
    if not all_tags and not any_tags and not not_any_tags:
        return []

    with get_connection() as conn:
        cursor = conn.cursor()

        # Build SQL query for tag filtering
        query_parts = []
        query_params = []

        # Base SQL query to get article summaries
        sql = """
        SELECT a.file_name, a.id 
        FROM article_summaries a
        """

        # Apply filename filter if provided
        if filenames:
            placeholders = ",".join(["?"] * len(filenames))
            sql += f" WHERE a.file_name IN ({placeholders})"
            query_params.extend(filenames)

        # Apply tag filters
        if all_tags:
            all_tags_conditions = []
            for tag in all_tags:
                sql += f"""
                INNER JOIN article_tags at_all{len(all_tags_conditions)} ON 
                    a.id = at_all{len(all_tags_conditions)}.article_id
                INNER JOIN tags t_all{len(all_tags_conditions)} ON 
                    at_all{len(all_tags_conditions)}.tag_id = t_all{len(all_tags_conditions)}.id 
                    AND t_all{len(all_tags_conditions)}.name = ?
                """
                query_params.append(tag)
                all_tags_conditions.append(
                    f"at_all{len(all_tags_conditions) - 1}.matches = 1"
                )

        # Add WHERE clause if needed
        if any_tags or not_any_tags:
            if "WHERE" not in sql:
                sql += " WHERE "
            else:
                sql += " AND "

            # Handle any_tags (OR logic)
            if any_tags:
                any_tags_conditions = []
                for tag in any_tags:
                    any_tags_conditions.append(
                        """
                    EXISTS (
                        SELECT 1 
                        FROM article_tags at_any
                        JOIN tags t_any ON at_any.tag_id = t_any.id
                        WHERE at_any.article_id = a.id 
                            AND t_any.name = ?
                            AND at_any.matches = 1
                    )
                    """
                    )
                    query_params.append(tag)

                sql += "(" + " OR ".join(any_tags_conditions) + ")"

            # Handle not_any_tags (NOT ANY logic)
            if not_any_tags:
                if any_tags:
                    sql += " AND "

                not_tags_conditions = []
                for tag in not_any_tags:
                    not_tags_conditions.append(
                        """
                    NOT EXISTS (
                        SELECT 1 
                        FROM article_tags at_not
                        JOIN tags t_not ON at_not.tag_id = t_not.id
                        WHERE at_not.article_id = a.id 
                            AND t_not.name = ?
                            AND at_not.matches = 1
                    )
                    """
                    )
                    query_params.append(tag)

                sql += "(" + " AND ".join(not_tags_conditions) + ")"

        # Execute the query
        cursor.execute(sql, query_params)
        return cursor.fetchall()


def get_articles_by_tag(tag_name: str) -> List[str]:
    """Get all article filenames that match a specific tag.

    Args:
        tag_name: Name of the tag

    Returns:
        List[str]: List of filenames
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        tag_id = get_tag_id_by_name(tag_name)

        if not tag_id:
            return []

        cursor.execute(
            """
            SELECT a.file_name 
            FROM article_summaries a
            JOIN article_tags at ON a.id = at.article_id
            WHERE at.tag_id = ? AND at.matches = 1
            """,
            (tag_id,),
        )

        return [row[0] for row in cursor.fetchall()]


def get_articles_without_tag(tag_name: str) -> List[str]:
    """Get all article filenames that do not match a specific tag.

    Args:
        tag_name: Name of the tag

    Returns:
        List[str]: List of filenames
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        tag_id = get_tag_id_by_name(tag_name)

        if not tag_id:
            return []

        cursor.execute(
            """
            SELECT a.file_name 
            FROM article_summaries a
            LEFT JOIN article_tags at ON a.id = at.article_id AND at.tag_id = ?
            WHERE at.article_id IS NULL OR at.matches = 0
            """,
            (tag_id,),
        )

        return [row[0] for row in cursor.fetchall()]


def get_articles_needing_tagging(
    max_articles: Optional[int] = None,
) -> List[Tuple[int, str, str, str]]:
    """Get articles that need tagging.

    Args:
        max_articles: Maximum number of articles to return

    Returns:
        List[Tuple[int, str, str, str]]: List of tuples containing article ID, file hash,
        filename, and summary
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT a.id, a.file_hash, a.file_name, a.summary 
            FROM article_summaries a
            WHERE NOT EXISTS (
                SELECT 1 FROM tags t
                WHERE EXISTS (
                    SELECT tag_id FROM article_tags WHERE article_id = a.id
                )
            )
            AND a.summary IS NOT NULL
            ORDER BY RANDOM()
        """

        if max_articles:
            query += f" LIMIT {max_articles}"

        cursor.execute(query)
        return cursor.fetchall()


def get_article_count_by_tag(tag_id: int) -> int:
    """Get the number of articles associated with a tag.

    Args:
        tag_id: ID of the tag

    Returns:
        int: Number of articles with this tag
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(article_id) as article_count
            FROM article_tags
            WHERE tag_id = ? AND matches = 1
            """,
            (tag_id,),
        )
        return cursor.fetchone()[0]


def get_all_tags_with_article_count() -> List[Tuple[int, str, int]]:
    """Get all tags with the count of articles for each.

    Returns:
        List[Tuple[int, str, int]]: List of tuples containing tag ID, name, and article count
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.id, t.name, COUNT(at.article_id) as article_count
            FROM tags t
            LEFT JOIN article_tags at ON t.id = at.tag_id AND at.matches = 1
            GROUP BY t.id, t.name
            """
        )
        return cursor.fetchall()


def get_articles_for_tag(tag_id: int) -> List[Tuple[int, str]]:
    """Get all articles associated with a tag.

    Args:
        tag_id: ID of the tag

    Returns:
        List[Tuple[int, str]]: List of tuples containing article ID and filename
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.id, a.file_name
            FROM article_summaries a
            JOIN article_tags at ON a.id = at.article_id
            WHERE at.tag_id = ? AND at.matches = 1
            """,
            (tag_id,),
        )
        return cursor.fetchall()


def clean_orphaned_database_items() -> Tuple[int, int]:
    """Clean orphaned database items.

    Removes:
    1. Orphaned tags (tags with no associated articles)
    2. Orphaned tag hashes (tag_hashes entries with no corresponding tag)

    Returns:
        Tuple[int, int]: Number of orphaned tags and tag hashes removed
    """
    orphaned_tags = remove_orphaned_tags()

    # Remove orphaned tag hashes
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM tag_hashes 
            WHERE tag_id NOT IN (
                SELECT id FROM tags
            )
            """
        )
        orphaned_hashes = cursor.rowcount
        conn.commit()

    return orphaned_tags, orphaned_hashes
