from PyQt6.QtCore import QStringListModel, Qt
from PyQt6.QtWidgets import QCompleter, QLineEdit

from purebrowser.data import history as history_mod


class UrlBar(QLineEdit):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._model = QStringListModel([], self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(self._completer)
        self.setMinimumHeight(34)
        self.setStyleSheet("padding: 6px 14px; font-size: 13px; border-radius: 8px;")
        self.textEdited.connect(self._refresh)

    def _refresh(self, text: str) -> None:
        rows = history_mod.suggest(self._conn, text, limit=10)
        items = [
            f"{r['title']} — {r['url']}" if r["title"] else r["url"]
            for r in rows
        ]
        self._model.setStringList(items)

        if not text or not items:
            self._completer.popup().hide()
            return

        self._completer.setCompletionPrefix(text)
        self._completer.complete()

    def pick_url_from_text(self) -> str:
        text = self.text()
        if " — " in text:
            return text.rsplit(" — ", 1)[1]
        return text