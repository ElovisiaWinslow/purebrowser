from urllib.parse import quote_plus

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QWidget, QVBoxLayout

DEFAULT_SEARCH = "https://cn.bing.com/search?q={q}"

# 页面把 Ctrl+F 交给浏览器的报信暗号。注入脚本只在网页自身未处理
# （未 preventDefault）时打印它；PurePage 拦截 console 后转成信号。
FIND_SENTINEL = "__PB_FIND__"


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
    fullscreen_toggled = pyqtSignal(bool)
    # 网页未处理 Ctrl+F 时发出（由注入脚本 → console 暗号转译）。
    shortcut_unhandled = pyqtSignal(str)

    def __init__(self, profile: QWebEngineProfile, parent=None):
        super().__init__(profile, parent)
        self.featurePermissionRequested.connect(self._deny)
        self.fullScreenRequested.connect(self._handle_fullscreen)

    def createWindow(self, _type):
        page = PurePage(self.profile())
        self.new_page_requested.emit(page)
        return page

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        # 只认暗号；其余 console 输出吞掉（默认实现也是静默）。
        if message == FIND_SENTINEL:
            self.shortcut_unhandled.emit("find")
            return
        super().javaScriptConsoleMessage(level, message, line_number, source_id)

    def _deny(self, origin, feature):
        self.setFeaturePermission(
            origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        )

    def _handle_fullscreen(self, request):
        # 只接受请求并转发信号。窗口状态的改变统一交给 MainWindow 处理。
        # 见 window.py 的 enter_fullscreen / exit_fullscreen。
        request.accept()
        self.fullscreen_toggled.emit(request.toggleOn())


class PureView(QWebEngineView):
    """接管右键：把 context-menu 请求与全局坐标交给 MainWindow 构建中文菜单。"""

    context_menu_requested = pyqtSignal(object, object)

    def contextMenuEvent(self, event) -> None:
        self.context_menu_requested.emit(self.lastContextMenuRequest(), event.globalPos())
        event.accept()


class Tab(QWidget):
    title_changed = pyqtSignal(str)
    url_changed = pyqtSignal(QUrl)
    load_started = pyqtSignal()
    load_finished = pyqtSignal(bool)
    page_loaded = pyqtSignal(str, str)
    new_page_requested = pyqtSignal(QWebEnginePage)
    fullscreen_toggled = pyqtSignal(bool)
    icon_changed = pyqtSignal(QIcon)

    def __init__(self, profile: QWebEngineProfile, parent=None, page: QWebEnginePage = None):
        super().__init__(parent)
        self.view = PureView(self)

        if page is None:
            page = PurePage(profile, self.view)
        else:
            page.setParent(self.view)
        page.new_page_requested.connect(self.new_page_requested)
        page.fullscreen_toggled.connect(self.fullscreen_toggled)
        self.view.setPage(page)
        self.view.page().setBackgroundColor(self.palette().window().color())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        self.view.titleChanged.connect(self.title_changed)
        self.view.urlChanged.connect(self.url_changed)
        self.view.loadStarted.connect(self.load_started)
        self.view.loadFinished.connect(self._on_finished)
        self.view.iconChanged.connect(self.icon_changed)

    def _on_finished(self, ok: bool) -> None:
        self.load_finished.emit(ok)
        if ok:
            self.page_loaded.emit(self.view.url().toString(), self.view.title())

    def load(self, url: QUrl) -> None:
        self.view.setUrl(url)

    def current_url(self) -> QUrl:
        return self.view.url()