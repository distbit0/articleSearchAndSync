import sqlite3
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set, Optional
from loguru import logger

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


def get_article_summary_by_hash(file_hash: str) -> Optional[str]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT summary FROM article_summaries WHERE file_hash = ?", (file_hash,)
        )
        row = cursor.fetchone()
    return row[0] if row else None


def get_article_id_by_hash(file_hash: str) -> Optional[int]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM article_summaries WHERE file_hash = ?", (file_hash,)
        )
        row = cursor.fetchone()
    return row[0] if row else None


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


def update_article_summary(
    file_hash: str,
    file_name: str,
    file_format: str,
    summary: str,
    extraction_method: str,
    word_count: int,
) -> int:
    with get_connection() as conn:
        article_id = get_article_id_by_hash(file_hash)
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
        existing_id = get_article_id_by_hash(file_hash)
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


def get_all_articles() -> List[Tuple[int, str]]:
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, file_name FROM article_summaries")
        return cursor.fetchall()


def get_articles_needing_summary() -> List[Tuple[str, str]]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT file_hash, file_name FROM article_summaries WHERE summary IS NULL OR summary = ''"
        )
        return cursor.fetchall()


def remove_article_by_id(article_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM article_tags WHERE article_id = ?", (article_id,))
        conn.execute("DELETE FROM article_summaries WHERE id = ?", (article_id,))
        conn.commit()


def remove_article_by_hash(file_hash: str) -> bool:
    article_id = get_article_id_by_hash(file_hash)
    if article_id:
        remove_article_by_id(article_id)
        return True
    return False


def get_articles_by_filename(filenames: List[str]) -> Dict[str, int]:
    if not filenames:
        return {}
    placeholders = ",".join("?" for _ in filenames)
    with get_connection() as conn:
        cursor = conn.execute(
            f"SELECT file_name, id FROM article_summaries WHERE file_name IN ({placeholders})",
            filenames,
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


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


def get_tag_details(tag_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, name, description, use_summary, any_tags, and_tags, not_any_tags FROM tags WHERE id = ?",
            (tag_id,),
        )
        row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "use_summary": bool(row[3]),
        "any_tags": json.loads(row[4]) if row[4] else [],
        "and_tags": json.loads(row[5]) if row[5] else [],
        "not_any_tags": json.loads(row[6]) if row[6] else [],
    }


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


def remove_article_tag(article_id: int, tag_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM article_tags WHERE article_id = ? AND tag_id = ?",
            (article_id, tag_id),
        )
        conn.commit()


def get_current_article_tags() -> Dict[int, Dict[str, List[Tuple[int, str]]]]:
    result = {}
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT at.article_id, t.name, t.id, at.matches FROM article_tags at JOIN tags t ON at.tag_id = t.id"
        )
        for article_id, tag_name, tag_id, matches in cursor.fetchall():
            result.setdefault(article_id, {"matching": [], "not_matching": []})
            if matches:
                result[article_id]["matching"].append((tag_id, tag_name))
            else:
                result[article_id]["not_matching"].append((tag_id, tag_name))
    return result


def remove_orphaned_tags() -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM article_tags)"
        )
        conn.commit()
    return cursor.rowcount


# Search Operations


def search_articles_by_tags(
    all_tags: List[str] = None,
    any_tags: List[str] = None,
    not_any_tags: List[str] = None,
    filenames: List[str] = None,
) -> List[Tuple[str, int]]:
    all_tags = all_tags or []
    any_tags = any_tags or []
    not_any_tags = not_any_tags or []
    if not (all_tags or any_tags or not_any_tags):
        return []
    query_params = []
    sql = "SELECT a.file_name, a.id FROM article_summaries a "
    if filenames:
        placeholders = ",".join("?" for _ in filenames)
        sql += f"WHERE a.file_name IN ({placeholders}) "
        query_params.extend(filenames)
    for i, tag in enumerate(all_tags):
        sql += f"""
        INNER JOIN article_tags at_all{i} ON a.id = at_all{i}.article_id AND at_all{i}.matches = 1
        INNER JOIN tags t_all{i} ON at_all{i}.tag_id = t_all{i}.id AND t_all{i}.name = ? 
        """
        query_params.append(tag)
    conditions = []
    if any_tags:
        any_conditions = []
        for tag in any_tags:
            any_conditions.append(
                "EXISTS (SELECT 1 FROM article_tags at_any JOIN tags t_any ON at_any.tag_id = t_any.id WHERE at_any.article_id = a.id AND t_any.name = ? AND at_any.matches = 1)"
            )
            query_params.append(tag)
        conditions.append("(" + " OR ".join(any_conditions) + ")")
    if not_any_tags:
        not_conditions = []
        for tag in not_any_tags:
            not_conditions.append(
                "NOT EXISTS (SELECT 1 FROM article_tags at_not JOIN tags t_not ON at_not.tag_id = t_not.id WHERE at_not.article_id = a.id AND t_not.name = ? AND at_not.matches = 1)"
            )
            query_params.append(tag)
        conditions.append("(" + " AND ".join(not_conditions) + ")")
    if conditions:
        sql += (
            "WHERE " + " AND ".join(conditions)
            if "WHERE" not in sql
            else " AND " + " AND ".join(conditions)
        )
    with get_connection() as conn:
        cursor = conn.execute(sql, query_params)
        return cursor.fetchall()


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
        AND a.summary IS NOT NULL
        ORDER BY RANDOM()
    """
    if max_articles:
        query += f" LIMIT {max_articles}"
    with get_connection() as conn:
        cursor = conn.execute(query)
        return cursor.fetchall()


def get_article_count_by_tag(tag_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(article_id) FROM article_tags WHERE tag_id = ? AND matches = 1",
            (tag_id,),
        )
        return cursor.fetchone()[0]


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
