from pathlib import Path

from PyQt6.QtCore import QUrl

NEWTAB_HTML = Path(__file__).resolve().parents[2] / "resources" / "newtab.html"
NEWTAB_URL = QUrl.fromLocalFile(str(NEWTAB_HTML))
NEWTAB_DISPLAY = "purebrowser://newtab"


def display_url(url: QUrl) -> str:
    if url.isLocalFile():
        try:
            if Path(url.toLocalFile()).resolve() == NEWTAB_HTML:
                return NEWTAB_DISPLAY
        except OSError:
            pass
    return url.toString()