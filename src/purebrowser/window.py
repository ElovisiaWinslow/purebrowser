import os
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWidgets import (
    QMainWindow,
    QMenu,
    QProgressBar,
    QTabWidget,
    QToolBar,
    QToolButton,
)

from . import bookmarks, history
from .downloads import DownloadManager
from .interceptor import Blocker
from .locations import settings_file
from .newtab import NEWTAB_URL, display_url
from .pages import PureBrowserSchemeHandler
from .profile import build_profile
from .settings import SEARCH_ENGINES, Settings
from .storage import connect
from .tab import Tab, to_url
from .urlbar import UrlBar


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path):
        super().__init__()
        self.setWindowTitle("PureBrowser")
        self.resize(1200, 800)

        self.data_dir = Path(data_dir)
        self.conn = connect(self.data_dir / "purebrowser.db")
        self.settings = Settings(settings_file())

        netlog_env = os.environ.get("PUREBROWSER_NETLOG", "").strip()
        netlog_path = Path(netlog_env) if netlog_env else None

        self.blocker = Blocker(self.settings, netlog_path=netlog_path)
        self.profile: QWebEngineProfile = build_profile(self.data_dir, self.blocker)
        self.scheme_handler = PureBrowserSchemeHandler(
            self.settings, self.conn, self.data_dir, self
        )
        self.profile.installUrlSchemeHandler(b"purebrowser", self.scheme_handler)

        self.downloads = DownloadManager(self.profile, self.settings, self)
        self.downloads.changed.connect(self._refresh_download_button)

        self.tabs = QTabWidget(self)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._sync_from_tab)
        self.setCentralWidget(self.tabs)

        self._build_toolbar()
        self._build_statusbar()
        self._install_shortcuts()

        self.new_tab(NEWTAB_URL)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        self.back = tb.addAction("←")
        self.back.triggered.connect(lambda: self._current().view.back())
        self.fwd = tb.addAction("→")
        self.fwd.triggered.connect(lambda: self._current().view.forward())
        self.reload = tb.addAction("⟳")
        self.reload.triggered.connect(lambda: self._current().view.reload())

        self.url_bar = UrlBar(self.conn)
        self.url_bar.returnPressed.connect(self._navigate)
        tb.addWidget(self.url_bar)

        self.bookmark_action = tb.addAction("☆")
        self.bookmark_action.triggered.connect(self._toggle_bookmark)

        self.history_btn = QToolButton(self)
        self.history_btn.setText("📜")
        self.history_btn.setToolTip("历史记录")
        self.history_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.history_menu = QMenu(self.history_btn)
        self.history_btn.setMenu(self.history_menu)
        self.history_menu.aboutToShow.connect(self._populate_history_menu)
        tb.addWidget(self.history_btn)

        self.bookmarks_btn = QToolButton(self)
        self.bookmarks_btn.setText("🔖")
        self.bookmarks_btn.setToolTip("书签")
        self.bookmarks_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bookmarks_menu = QMenu(self.bookmarks_btn)
        self.bookmarks_btn.setMenu(self.bookmarks_menu)
        self.bookmarks_menu.aboutToShow.connect(self._populate_bookmarks_menu)
        tb.addWidget(self.bookmarks_btn)

        self.download_btn = QToolButton(self)
        self.download_btn.setText("⬇")
        self.download_btn.setToolTip("下载")
        self.download_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.download_menu = QMenu(self.download_btn)
        self.download_btn.setMenu(self.download_menu)
        self.download_menu.aboutToShow.connect(self._populate_download_menu)
        tb.addWidget(self.download_btn)

        new_tab = tb.addAction("+")
        new_tab.triggered.connect(lambda: self.new_tab(NEWTAB_URL))

        settings_action = tb.addAction("⚙")
        settings_action.triggered.connect(self._open_settings)

    def _build_statusbar(self) -> None:
        self.progress = QProgressBar(self)
        self.progress.setMaximumWidth(160)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(
            lambda: self.new_tab(NEWTAB_URL)
        )
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            lambda: self._close_tab(self.tabs.currentIndex())
        )
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._focus_url_bar)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(
            lambda: self._current().view.reload()
        )
        QShortcut(QKeySequence("F5"), self).activated.connect(
            lambda: self._current().view.reload()
        )
        QShortcut(QKeySequence("Alt+Left"), self).activated.connect(
            lambda: self._current().view.back()
        )
        QShortcut(QKeySequence("Alt+Right"), self).activated.connect(
            lambda: self._current().view.forward()
        )
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self._toggle_bookmark)
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(
            lambda: self.new_tab(QUrl("purebrowser://history"))
        )
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            lambda: self.bookmarks_btn.showMenu()
        )
        QShortcut(QKeySequence("Ctrl+J"), self).activated.connect(
            lambda: self.download_btn.showMenu()
        )

    def _focus_url_bar(self) -> None:
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    def _populate_history_menu(self) -> None:
        self.history_menu.clear()
        rows = history.recent(self.conn, limit=30)
        if not rows:
            a = self.history_menu.addAction("暂无历史记录")
            a.setEnabled(False)
        else:
            for r in rows:
                title = r["title"] or r["url"]
                if len(title) > 60:
                    title = title[:57] + "..."
                action = self.history_menu.addAction(title)
                url = r["url"]
                action.triggered.connect(
                    lambda checked=False, u=url: self._open_in_current_tab(u)
                )
        self.history_menu.addSeparator()
        view_all = self.history_menu.addAction("查看全部历史记录")
        view_all.triggered.connect(lambda: self.new_tab(QUrl("purebrowser://history")))

    def _populate_bookmarks_menu(self) -> None:
        self.bookmarks_menu.clear()
        rows = bookmarks.list_all(self.conn)
        if not rows:
            a = self.bookmarks_menu.addAction("暂无书签")
            a.setEnabled(False)
            return
        for r in rows:
            title = r["title"] or r["url"]
            if len(title) > 60:
                title = title[:57] + "..."
            action = self.bookmarks_menu.addAction(title)
            url = r["url"]
            action.triggered.connect(
                lambda checked=False, u=url: self._open_in_current_tab(u)
            )
        self.bookmarks_menu.addSeparator()
        clear_all = self.bookmarks_menu.addAction("清空所有书签")
        clear_all.triggered.connect(self._clear_bookmarks)

    def _populate_download_menu(self) -> None:
        self.download_menu.clear()
        open_folder = self.download_menu.addAction("打开下载文件夹")
        open_folder.triggered.connect(self.downloads.open_folder)
        self.download_menu.addSeparator()
        if not self.downloads.has_any():
            a = self.download_menu.addAction("暂无下载")
            a.setEnabled(False)
            return
        for rec in reversed(self.downloads.records):
            label = rec["filename"]
            if rec["canceled"]:
                label += "  ✗"
            elif rec["finished"]:
                label += "  ✓"
            else:
                total = rec["total"] or 1
                pct = int(rec["received"] * 100 / total)
                label += f"  {pct}%"
            a = self.download_menu.addAction(label)
            a.setEnabled(False)

    def _refresh_download_button(self) -> None:
        n = self.downloads.active_count()
        self.download_btn.setText(f"⬇{n}" if n else "⬇")

    def _open_in_current_tab(self, url: str) -> None:
        self._current().load(QUrl(url))

    def _clear_bookmarks(self) -> None:
        for r in bookmarks.list_all(self.conn):
            bookmarks.remove(self.conn, r["url"])
        self._refresh_bookmark_icon()

    def new_tab(self, url: QUrl, page: QWebEnginePage = None) -> Tab:
        tab = Tab(self.profile, self, page=page)
        idx = self.tabs.addTab(tab, "新标签页")
        self.tabs.setCurrentIndex(idx)
        tab.title_changed.connect(lambda t: self._set_tab_title(tab, t))
        tab.url_changed.connect(lambda u: self._on_url_changed(tab, u))
        tab.load_started.connect(self._on_load_started)
        tab.load_finished.connect(self._on_load_finished)
        tab.page_loaded.connect(self._on_page_loaded)
        tab.new_page_requested.connect(self._on_new_page_requested)
        if page is None:
            tab.load(url)
        return tab

    def _on_new_page_requested(self, page: QWebEnginePage) -> None:
        self.new_tab(QUrl("about:blank"), page=page)

    def _close_tab(self, idx: int) -> None:
        if idx < 0:
            return
        if self.tabs.count() <= 1:
            return
        w = self.tabs.widget(idx)
        self.tabs.removeTab(idx)
        w.deleteLater()

    def _current(self) -> Tab:
        return self.tabs.currentWidget()  # type: ignore[return-value]

    def _set_tab_title(self, tab: Tab, title: str) -> None:
        i = self.tabs.indexOf(tab)
        if i >= 0:
            self.tabs.setTabText(i, title[:24] or "新标签页")

    def _on_url_changed(self, tab: Tab, url: QUrl) -> None:
        if tab is self.tabs.currentWidget():
            self.url_bar.setText(display_url(url))
            self.url_bar.setCursorPosition(0)

    def _sync_from_tab(self, _idx: int) -> None:
        tab = self.tabs.currentWidget()
        if isinstance(tab, Tab):
            self.url_bar.setText(display_url(tab.current_url()))
            self._refresh_bookmark_icon()

    def _navigate(self) -> None:
        text = self.url_bar.pick_url_from_text()
        engine = self.settings.get("search_engine", "bing")
        template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["bing"])
        self._current().load(to_url(text, template))

    def _open_settings(self) -> None:
        self.new_tab(QUrl("purebrowser://settings"))

    def _on_page_loaded(self, url: str, title: str) -> None:
        history.add_visit(self.conn, url, title)

    def _toggle_bookmark(self) -> None:
        tab = self._current()
        url = tab.current_url().toString()
        if not url or url == "about:blank":
            return
        if bookmarks.is_bookmarked(self.conn, url):
            bookmarks.remove(self.conn, url)
        else:
            bookmarks.add(self.conn, url, tab.view.title())
        self._refresh_bookmark_icon()

    def _refresh_bookmark_icon(self) -> None:
        url = self._current().current_url().toString()
        if url and bookmarks.is_bookmarked(self.conn, url):
            self.bookmark_action.setText("★")
        else:
            self.bookmark_action.setText("☆")

    def _on_load_started(self) -> None:
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

    def _on_load_finished(self, ok: bool) -> None:
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)

    def closeEvent(self, event) -> None:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, Tab):
                w.view.setPage(None)
        self.blocker.close()
        self.conn.close()
        super().closeEvent(event)