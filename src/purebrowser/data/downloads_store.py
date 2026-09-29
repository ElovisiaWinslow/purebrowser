"""下载记录的持久化（SQLite）。不负责文件本身，只记元数据。"""
import sqlite3
import time

TERMINAL_STATES = ("completed", "cancelled", "interrupted")


def save(conn: sqlite3.Connection, rec: dict) -> int:
    """插入一条下载记录，返回自增 id。"""
    cur = conn.execute(
        "INSERT INTO downloads "
        "(url, filename, path, total, received, state, interrupt_reason, "
        " created_at, finished_at, mime) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            rec.get("url") or "",
            rec.get("filename") or "",
            rec.get("path") or "",
            int(rec.get("total") or 0),
            int(rec.get("received") or 0),
            rec.get("state_text") or "inprogress",
            rec.get("interrupt_reason") or "",
            int(rec.get("created_at") or time.time()),
            rec.get("finished_at"),
            rec.get("mime") or "",
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def update(conn: sqlite3.Connection, db_id: int, state: str, received: int, total: int,
           interrupt_reason: str, finished_at: int | None = None) -> None:
    conn.execute(
        "UPDATE downloads SET state = ?, received = ?, total = ?, "
        "interrupt_reason = ?, finished_at = ? WHERE id = ?",
        (state, int(received or 0), int(total or 0), interrupt_reason or "",
         finished_at, int(db_id)),
    )
    conn.commit()


def list_recent(conn: sqlite3.Connection, limit: int = 200):
    cur = conn.execute(
        "SELECT id, url, filename, path, total, received, state, interrupt_reason, "
        "created_at, finished_at, mime FROM downloads "
        "ORDER BY created_at DESC, id DESC LIMIT ?",
        (limit,),
    )
    return cur.fetchall()


def remove(conn: sqlite3.Connection, db_id: int) -> None:
    conn.execute("DELETE FROM downloads WHERE id = ?", (int(db_id),))
    conn.commit()


def prune(conn: sqlite3.Connection, keep: int = 200) -> None:
    conn.execute(
        "DELETE FROM downloads WHERE id NOT IN "
        "(SELECT id FROM downloads ORDER BY created_at DESC, id DESC LIMIT ?)",
        (keep,),
    )
    conn.commit()


def mark_inprogress_as_interrupted(conn: sqlite3.Connection) -> None:
    """启动时调用：上次会话遗留的 '进行中' 无 request，无法继续，标记为已中断。"""
    conn.execute(
        "UPDATE downloads SET state = 'interrupted' WHERE state = 'inprogress'"
    )
    conn.commit()
