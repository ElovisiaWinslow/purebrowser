import sqlite3
import time
from urllib.parse import urlparse

SKIP_SCHEMES = ("file", "about", "data", "blob", "purebrowser", "chrome")


def add_visit(conn: sqlite3.Connection, url: str, title: str) -> None:
    if not url:
        return
    scheme = urlparse(url).scheme
    if scheme in SKIP_SCHEMES:
        return
    host = urlparse(url).hostname or ""
    now = int(time.time())
    cur = conn.execute("SELECT id, visit_count FROM history WHERE url = ?", (url,))
    row = cur.fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO history (url, title, host, visited_at, visit_count) "
            "VALUES (?, ?, ?, ?, 1)",
            (url, title or url, host, now),
        )
    else:
        conn.execute(
            "UPDATE history SET title = COALESCE(NULLIF(?, ''), title), "
            "visited_at = ?, visit_count = visit_count + 1 WHERE id = ?",
            (title, now, row["id"]),
        )
    conn.commit()


def recent(conn: sqlite3.Connection, limit: int = 200):
    cur = conn.execute(
        "SELECT id, url, title, host, visited_at, visit_count FROM history "
        "ORDER BY visited_at DESC LIMIT ?",
        (limit,),
    )
    return cur.fetchall()


def remove_by_id(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute("DELETE FROM history WHERE id = ?", (row_id,))
    conn.commit()


def suggest(conn: sqlite3.Connection, prefix: str, limit: int = 10):
    if not prefix:
        return []
    like = f"%{prefix}%"
    cur = conn.execute(
        "SELECT url, title FROM history "
        "WHERE url LIKE ? OR title LIKE ? "
        "ORDER BY visit_count DESC, visited_at DESC LIMIT ?",
        (like, like, limit),
    )
    return cur.fetchall()


def clear(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM history")
    conn.commit()