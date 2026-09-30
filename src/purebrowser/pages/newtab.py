from PyQt6.QtCore import QUrl

NEWTAB_URL = QUrl("purebrowser://newtab")
NEWTAB_DISPLAY = "purebrowser://newtab"


def display_url(url: QUrl) -> str:
    # purebrowser:// 原样显示（不再需要把 file:// 映射成 newtab）
    return url.toString()