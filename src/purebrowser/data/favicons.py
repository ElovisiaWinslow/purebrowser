"""Favicon 缓存：以 host 为键，存 PNG 字节。仅从 view.iconChanged 捕获，不使用
QWebEngineProfile.requestIconForPageURL（该 API 在本构建会崩溃）。"""
import sqlite3
import time

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap

MAX_BYTES = 2048
NORMAL_SIZE = 32


def _encode(icon: QIcon, size: int) -> bytes | None:
    pixmap = icon.pixmap(QSize(size, size))
    if pixmap.isNull():
        return None
    if pixmap.width() != size or pixmap.height() != size:
        pixmap = pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    data = QByteArray()
    buf = QBuffer(data)
    if not buf.open(QIODevice.OpenModeFlag.WriteOnly):
        return None
    try:
        pixmap.save(buf, "PNG")
    finally:
        buf.close()
    raw = bytes(data)
    return raw or None


def icon_to_png(icon: QIcon | None, size: int = NORMAL_SIZE) -> bytes | None:
    """把 QIcon 归一化为 PNG 字节；优先 size，超 2KB 时降级到 16px。"""
    if icon is None or icon.isNull():
        return None
    for candidate in (size, 16):
        raw = _encode(icon, candidate)
        if raw is not None and len(raw) <= MAX_BYTES:
            return raw
    return None


def save(conn: sqlite3.Connection, host: str, png_bytes: bytes | None) -> bool:
    """幂等写入：同 host 同字节不重复写。返回是否发生写入。"""
    if not host or not png_bytes or len(png_bytes) > MAX_BYTES:
        return False
    cur = conn.execute("SELECT data FROM favicons WHERE host = ?", (host,))
    row = cur.fetchone()
    if row is not None and bytes(row["data"]) == png_bytes:
        return False
    conn.execute(
        "INSERT OR REPLACE INTO favicons (host, data, fetched_at) VALUES (?, ?, ?)",
        (host, png_bytes, int(time.time())),
    )
    conn.commit()
    return True


def get(conn: sqlite3.Connection, host: str) -> QPixmap | None:
    """读缓存并解码为 QPixmap；无缓存/解码失败返回 None。"""
    if not host:
        return None
    cur = conn.execute("SELECT data FROM favicons WHERE host = ?", (host,))
    row = cur.fetchone()
    if row is None:
        return None
    pixmap = QPixmap()
    if not pixmap.loadFromData(bytes(row["data"])):
        return None
    return pixmap
