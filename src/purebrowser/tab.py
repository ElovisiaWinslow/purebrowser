from urllib.parse import quote_plus

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget, QVBoxLayout

DEFAULT_SEARCH = "https://cn.bing.com/search?q={q}"


def to_url(text: str, search_template: str = DEFAULT_SEARCH) -> QUrl:
    text = text.strip()
    if not text:
        return QUrl("about:blank")
    if text.startswith("purebrowser://"):
        return QUrl(text)
    if " " in text or "." not in text:
        return QUrl(search_template.format(q=quote_plus(text)))
    if "://" not in text:
        text = "https://" + text
    return QUrl(text)


class PurePage(QWebEnginePage):
    new_page_requested = pyqtSignal(QWebEnginePage)

    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(profile, parent)
        self.featurePermissionRequested.connect(self._deny)

    def createWindow(self, _type):
        page = PurePage(self.profile())
        self.new_page_requested.emit(page)
        return page

    def _deny(self, origin, feature):
        self.setFeaturePermission(
            origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        )


class Tab(QWidget):
    title_changed = pyqtSignal(str)
    url_changed = pyqtSignal(QUrl)
    load_started = pyqtSignal()
    load_finished = pyqtSignal(bool)
    page_loaded = pyqtSignal(str, str)
    new_page_requested = pyqtSignal(QWebEnginePage)

    def __init__(self, profile: QWebEngineProfile, parent=None, page: QWebEnginePage = None):
        super().__init__(parent)
        self.view = QWebEngineView(self)

        if page is None:
            page = PurePage(profile, self.view)
        else:
            page.setParent(self.view)
        page.new_page_requested.connect(self.new_page_requested)
        self.view.setPage(page)
        self.view.page().setBackgroundColor(self.palette().window().color())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self.view.titleChanged.connect(self.title_changed)
        self.view.urlChanged.connect(self.url_changed)
        self.view.loadStarted.connect(self.load_started)
        self.view.loadFinished.connect(self._on_finished)

    def _on_finished(self, ok: bool) -> None:
        self.load_finished.emit(ok)
        if ok:
            self.page_loaded.emit(self.view.url().toString(), self.view.title())

    def load(self, url: QUrl) -> None:
        self.view.setUrl(url)

    def current_url(self) -> QUrl:
        return self.view.url()