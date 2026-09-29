import sqlite3
import time


def add(conn: sqlite3.Connection, url: str, title: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO bookmarks (url, title, created_at) VALUES (?, ?, ?)",
        (url, title or url, int(time.time())),
    )
    conn.commit()


def remove(conn: sqlite3.Connection, url: str) -> None:
    conn.execute("DELETE FROM bookmarks WHERE url = ?", (url,))
    conn.commit()


def is_bookmarked(conn: sqlite3.Connection, url: str) -> bool:
    cur = conn.execute("SELECT 1 FROM bookmarks WHERE url = ?", (url,))
    return cur.fetchone() is not None


def list_all(conn: sqlite3.Connection):
    cur = conn.execute(
        "SELECT url, title, created_at FROM bookmarks ORDER BY created_at DESC"
    )
    return cur.fetchall()