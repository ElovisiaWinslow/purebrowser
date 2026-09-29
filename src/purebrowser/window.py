import os
import time
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl
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

        # 全屏控制器状态（唯一来源）
        self._restore_maximized = False
        self._fullscreen_source = None

        # 全屏时序调试探针（PUREBROWSER_FS_DEBUG=1 开启）
        self._fs_debug = bool(os.environ.get("PUREBROWSER_FS_DEBUG", "").strip())
        self._fs_t0 = None
        self._fs_probe_connected = False

        # 退出全屏恢复最大化时，等待最大化状态确认后再显示窗口
        self._pending_restore_show = False

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
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet("QTabWidget::pane { border: 0; }")
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._sync_from_tab)
        self.setCentralWidget(self.tabs)

        self._build_toolbar()
        self._build_statusbar()
        self._install_shortcuts()

        self.new_tab(NEWTAB_URL)

    # ---------- UI ----------
    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("Main", self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)

        self.back = self.toolbar.addAction("←")
        self.back.triggered.connect(lambda: self._current().view.back())
        self.fwd = self.toolbar.addAction("→")
        self.fwd.triggered.connect(lambda: self._current().view.forward())
        self.reload = self.toolbar.addAction("⟳")
        self.reload.triggered.connect(lambda: self._current().view.reload())

        self.url_bar = UrlBar(self.conn)
        self.url_bar.returnPressed.connect(self._navigate)
        self.toolbar.addWidget(self.url_bar)

        self.bookmark_action = self.toolbar.addAction("☆")
        self.bookmark_action.triggered.connect(self._toggle_bookmark)

        self.history_btn = QToolButton(self)
        self.history_btn.setText("📜")
        self.history_btn.setToolTip("历史记录")
        self.history_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.history_menu = QMenu(self.history_btn)
        self.history_btn.setMenu(self.history_menu)
        self.history_menu.aboutToShow.connect(self._populate_history_menu)
        self.toolbar.addWidget(self.history_btn)

        self.bookmarks_btn = QToolButton(self)
        self.bookmarks_btn.setText("🔖")
        self.bookmarks_btn.setToolTip("书签")
        self.bookmarks_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bookmarks_menu = QMenu(self.bookmarks_btn)
        self.bookmarks_btn.setMenu(self.bookmarks_menu)
        self.bookmarks_menu.aboutToShow.connect(self._populate_bookmarks_menu)
        self.toolbar.addWidget(self.bookmarks_btn)

        self.download_btn = QToolButton(self)
        self.download_btn.setText("⬇")
        self.download_btn.setToolTip("下载")
        self.download_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.download_menu = QMenu(self.download_btn)
        self.download_btn.setMenu(self.download_menu)
        self.download_menu.aboutToShow.connect(self._populate_download_menu)
        self.toolbar.addWidget(self.download_btn)

        new_tab = self.toolbar.addAction("+")
        new_tab.triggered.connect(lambda: self.new_tab(NEWTAB_URL))

        settings_action = self.toolbar.addAction("⚙")
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
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._exit_fullscreen)

    def _focus_url_bar(self) -> None:
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    # ---------- 全屏时序调试探针（PUREBROWSER_FS_DEBUG=1 开启） ----------
    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._fs_probe_connected:
            wh = self.windowHandle()
            if wh is not None:
                wh.windowStateChanged.connect(self._on_window_state_changed)
                self._fs_probe_connected = True
                self._fs_log("windowStateChanged probe connected")

    def _fs_log(self, msg: str) -> None:
        if not self._fs_debug:
            return
        if self._fs_t0 is None:
            self._fs_t0 = time.monotonic()
        elapsed_ms = (time.monotonic() - self._fs_t0) * 1000
        print(f"[FS {elapsed_ms:9.2f} ms] {msg}", flush=True)

    def _on_window_state_changed(self, state) -> None:
        names = []
        if state & Qt.WindowState.WindowFullScreen:
            names.append("FullScreen")
        if state & Qt.WindowState.WindowMaximized:
            names.append("Maximized")
        if state & Qt.WindowState.WindowMinimized:
            names.append("Minimized")
        if state & Qt.WindowState.WindowActive:
            names.append("Active")
        if not names:
            names.append("NoState(Normal)")
        raw = getattr(state, "value", state)
        self._fs_log(f"windowStateChanged -> {'|'.join(names)} (raw={raw})")

        if self._pending_restore_show and (state & Qt.WindowState.WindowMaximized):
            self._pending_restore_show = False
            self.show()
            self._show_chrome()

    def _force_restore_show(self) -> None:
        if self._pending_restore_show:
            self._pending_restore_show = False
            self.show()
            self._show_chrome()

    # ---------- fullscreen 统一控制器 ----------
    def _hide_chrome(self) -> None:
        self.toolbar.hide()
        self.tabs.tabBar().hide()
        self.statusBar().hide()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 0; margin: 0; padding: 0; }"
        )

    def _show_chrome(self) -> None:
        self.toolbar.show()
        self.tabs.tabBar().show()
        self.statusBar().show()
        self.tabs.setStyleSheet("QTabWidget::pane { border: 0; }")

    def enter_fullscreen(self, source: str = "video") -> None:
        """统一的全屏入口。source: 'video' | 'hotkey'，仅用于标记，不影响行为。"""
        if self.isFullScreen():
            return
        self._restore_maximized = self.isMaximized()
        self._fullscreen_source = source
        self._fs_log(
            f"enter_fullscreen source={source} restore_maximized={self._restore_maximized}"
        )
        self.showFullScreen()
        self._hide_chrome()

    def exit_fullscreen(self) -> None:
        """统一的退出全屏入口。"""
        if not self.isFullScreen():
            return
        self._fs_log(
            f"exit_fullscreen restore_maximized={self._restore_maximized}"
        )
        if self._restore_maximized:
            # Windows/Qt 从全屏退出会分两步：全屏 -> 普通 -> 最大化，
            # 中间"普通窗口"帧会被 DWM 合成出来，形成可见的中间态。
            # 先隐藏窗口，切换状态，等最大化状态确认后再显示，
            # 保证中间帧永远不会被合成出来。
            self.hide()
            self._pending_restore_show = True
            self.setWindowState(Qt.WindowState.WindowMaximized)
            QTimer.singleShot(150, self._force_restore_show)
        else:
            self.showNormal()
            self._show_chrome()
        self._restore_maximized = False
        self._fullscreen_source = None

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self.enter_fullscreen(source="hotkey")

    def _exit_fullscreen(self) -> None:
        self.exit_fullscreen()

    def _on_fullscreen_toggled(self, on: bool) -> None:
        """视频站通过 fullScreenRequested 触发的入口，转发到统一控制器。"""
        if on:
            self.enter_fullscreen(source="video")
        else:
            self.exit_fullscreen()

    # ---------- menus ----------
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

    # ---------- tab management ----------
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
        tab.fullscreen_toggled.connect(self._on_fullscreen_toggled)
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

    # ---------- navigation ----------
    def _navigate(self) -> None:
        text = self.url_bar.pick_url_from_text()
        engine = self.settings.get("search_engine", "bing")
        template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["bing"])
        self._current().load(to_url(text, template))

    def _open_settings(self) -> None:
        self.new_tab(QUrl("purebrowser://settings"))

    # ---------- history ----------
    def _on_page_loaded(self, url: str, title: str) -> None:
        history.add_visit(self.conn, url, title)

    # ---------- bookmarks ----------
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

    # ---------- loading ----------
    def _on_load_started(self) -> None:
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

    def _on_load_finished(self, ok: bool) -> None:
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)

    # ---------- close ----------
    def closeEvent(self, event) -> None:
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, Tab):
                w.view.setPage(None)
        self.blocker.close()
        self.conn.close()
        super().closeEvent(event)