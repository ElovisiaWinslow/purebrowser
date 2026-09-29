import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path

from PyQt6.QtCore import QPoint, QSize, Qt, QUrl
from PyQt6.QtGui import QColor, QFontMetrics, QKeySequence, QShortcut
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QMainWindow,
    QMenu,
    QProgressBar,
    QTabBar,
    QTabWidget,
    QToolBar,
    QToolButton,
)

from purebrowser.core.interceptor import Blocker
from purebrowser.core.locations import settings_file
from purebrowser.core.profile import build_profile
from purebrowser.core.settings import SEARCH_ENGINES, Settings
from purebrowser.data import bookmarks, history
from purebrowser.pages.downloads import DownloadManager
from purebrowser.pages.newtab import NEWTAB_URL, display_url
from purebrowser.pages.pages import PureBrowserSchemeHandler
from purebrowser.data.storage import connect
from purebrowser.ui import icons
from purebrowser.ui import theme as theme_mod
from purebrowser.ui.tab import Tab, to_url
from purebrowser.ui.tabbar import AdaptiveTabBar
from purebrowser.ui.urlbar import UrlBar

# ---------------------------------------------------------------------------
# 原生 Win32 全屏支持（ctypes，标准库，不引入新依赖）。
# 仅 Windows 有效。进入/退出都走原生 API，不再混用 Qt 的 show* / setWindowState，
# 否则两套状态机会失配。
# ---------------------------------------------------------------------------
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    _user32 = ctypes.windll.user32

    GWL_STYLE = -16

    WS_OVERLAPPEDWINDOW = 0x00CF0000
    WS_CAPTION = 0x00C00000
    WS_THICKFRAME = 0x00040000
    WS_MINIMIZEBOX = 0x00020000
    WS_MAXIMIZEBOX = 0x00010000
    WS_SYSMENU = 0x00080000

    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020
    HWND_TOP = 0

    MONITOR_DEFAULTTONEAREST = 0x00000002

    class _WINDOWPLACEMENT(ctypes.Structure):
        _fields_ = [
            ("length", wintypes.UINT),
            ("flags", wintypes.UINT),
            ("showCmd", wintypes.UINT),
            ("ptMinPosition", wintypes.POINT),
            ("ptMaxPosition", wintypes.POINT),
            ("rcNormalPosition", wintypes.RECT),
        ]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    _user32.GetWindowLongPtrW.restype = ctypes.c_void_p
    _user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.SetWindowLongPtrW.restype = ctypes.c_void_p
    _user32.SetWindowLongPtrW.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_void_p,
    ]
    _user32.GetWindowPlacement.restype = wintypes.BOOL
    _user32.GetWindowPlacement.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(_WINDOWPLACEMENT),
    ]
    _user32.SetWindowPlacement.restype = wintypes.BOOL
    _user32.SetWindowPlacement.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(_WINDOWPLACEMENT),
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    _user32.MonitorFromWindow.restype = ctypes.c_void_p
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.GetMonitorInfoW.restype = wintypes.BOOL
    _user32.GetMonitorInfoW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(_MONITORINFO),
    ]


def _fmt_ptr(value) -> str:
    if value is None:
        return "0x0(None)"
    return f"0x{int(value) & 0xFFFFFFFFFFFFFFFF:016X}"


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path):
        super().__init__()
        self.setWindowTitle("PureBrowser")
        self.resize(1200, 800)

        # 全屏控制器状态（唯一来源）。原生 API 改窗口后 Qt 不知情，
        # 因此 isFullScreen() 恒为 False，用这个标志替代。
        self._is_fullscreen = False
        self._fullscreen_source = None
        self._saved_placement = None
        self._saved_style = None

        # 全屏时序调试探针（PUREBROWSER_FS_DEBUG=1 开启）
        self._fs_debug = bool(os.environ.get("PUREBROWSER_FS_DEBUG", "").strip())
        self._fs_t0 = None
        self._fs_probe_connected = False

        self.data_dir = Path(data_dir)
        self.conn = connect(self.data_dir / "purebrowser.db")
        self.settings = Settings(settings_file())
        self.theme = theme_mod.resolve_theme(self.settings.get("theme", "system"))
        self._tab_full_titles: dict = {}

        netlog_env = os.environ.get("PUREBROWSER_NETLOG", "").strip()
        netlog_path = Path(netlog_env) if netlog_env else None

        self.blocker = Blocker(self.settings, netlog_path=netlog_path)
        self.profile: QWebEngineProfile = build_profile(self.data_dir, self.blocker)
        self.scheme_handler = PureBrowserSchemeHandler(
            self.settings, self.conn, self.data_dir, self, theme=self.theme
        )
        self.profile.installUrlSchemeHandler(b"purebrowser", self.scheme_handler)

        self.downloads = DownloadManager(self.profile, self.settings, self)
        self.downloads.changed.connect(self._refresh_download_button)

        self.tabs = QTabWidget(self)
        self.tabs.setTabBar(AdaptiveTabBar(self.tabs))
        self.tabs.setTabsClosable(False)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.tabBar().setMinimumHeight(38)
        self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setStyleSheet("QTabWidget::pane { border: 0; }")
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._sync_from_tab)
        self.setCentralWidget(self.tabs)

        self._build_toolbar()
        self._build_statusbar()
        self._build_tab_plus()
        self._install_shortcuts()

        self.new_tab(NEWTAB_URL)

        self._sync_tab_visibility()

    # ---------- UI ----------
    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("Main", self)
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(18, 18))
        self.toolbar.setFixedHeight(46)
        self.addToolBar(self.toolbar)

        self.back = self.toolbar.addAction(icons.icon("back", self.theme.text), "")
        self.back.setToolTip("后退")
        self.back.triggered.connect(lambda: self._current().view.back())
        self.fwd = self.toolbar.addAction(icons.icon("forward", self.theme.text), "")
        self.fwd.setToolTip("前进")
        self.fwd.triggered.connect(lambda: self._current().view.forward())
        self.reload = self.toolbar.addAction(icons.icon("reload", self.theme.text), "")
        self.reload.setToolTip("刷新")
        self.reload.triggered.connect(lambda: self._current().view.reload())

        self.url_bar = UrlBar(self.conn)
        self.url_bar.returnPressed.connect(self._navigate)
        self.toolbar.addWidget(self.url_bar)

        self.bookmark_action = self.toolbar.addAction(icons.icon("star", self.theme.text), "")
        self.bookmark_action.setToolTip("收藏 / 取消收藏")
        self.bookmark_action.triggered.connect(self._toggle_bookmark)

        self.history_btn = QToolButton(self)
        self.history_btn.setIcon(icons.icon("clock", self.theme.text))
        self.history_btn.setToolTip("历史记录")
        self.history_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.history_menu = QMenu(self.history_btn)
        self.history_btn.setMenu(self.history_menu)
        self.history_menu.aboutToShow.connect(self._populate_history_menu)
        self.toolbar.addWidget(self.history_btn)

        self.bookmarks_btn = QToolButton(self)
        self.bookmarks_btn.setIcon(icons.icon("bookmark", self.theme.text))
        self.bookmarks_btn.setToolTip("书签")
        self.bookmarks_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bookmarks_menu = QMenu(self.bookmarks_btn)
        self.bookmarks_btn.setMenu(self.bookmarks_menu)
        self.bookmarks_menu.aboutToShow.connect(self._populate_bookmarks_menu)
        self.toolbar.addWidget(self.bookmarks_btn)

        self.download_btn = QToolButton(self)
        self.download_btn.setIcon(icons.icon("download", self.theme.text))
        self.download_btn.setToolTip("下载")
        self.download_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.download_menu = QMenu(self.download_btn)
        self.download_btn.setMenu(self.download_menu)
        self.download_menu.aboutToShow.connect(self._populate_download_menu)
        self.toolbar.addWidget(self.download_btn)

        settings_action = self.toolbar.addAction(icons.icon("settings", self.theme.text), "")
        settings_action.setToolTip("设置")
        settings_action.triggered.connect(self._open_settings)

        self._apply_shadow(self.toolbar)
        self._apply_shadow(self.history_menu)
        self._apply_shadow(self.bookmarks_menu)
        self._apply_shadow(self.download_menu)

    @staticmethod
    def _apply_shadow(widget, blur: int = 12, dy: int = 2, alpha: int = 30) -> None:
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, dy)
        effect.setColor(QColor(0, 0, 0, alpha))
        widget.setGraphicsEffect(effect)

    def _build_statusbar(self) -> None:
        self.progress = QProgressBar(self)
        self.progress.setMaximumWidth(160)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

    def _build_tab_plus(self) -> None:
        """+ 按钮是 self.tabs 的子控件，动态跟随最后一个标签（带上限）。"""
        self.tab_plus = QToolButton(self.tabs)
        self.tab_plus.setObjectName("tabPlus")
        self.tab_plus.setText("")
        self.tab_plus.setIcon(icons.icon("plus", self.theme.subtext, 16))
        self.tab_plus.setIconSize(QSize(16, 16))
        self.tab_plus.setToolTip("新标签页")
        self.tab_plus.setFixedSize(28, 28)
        self.tab_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_plus.clicked.connect(lambda: self.new_tab(NEWTAB_URL))
        bar = self.tabs.tabBar()
        bar.tabMoved.connect(self._position_tab_plus)
        bar.currentChanged.connect(self._position_tab_plus)
        self._position_tab_plus()

    def _install_tab_close(self, tab: Tab) -> None:
        """给单个标签装自定义关闭按钮（细线 SVG，hover 高亮）。"""
        bar = self.tabs.tabBar()
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        btn = QToolButton(bar)
        btn.setObjectName("tabClose")
        btn.setIcon(icons.icon("close", self.theme.subtext, 12))
        btn.setIconSize(QSize(12, 12))
        btn.setFixedSize(18, 18)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("关闭标签页")
        btn.clicked.connect(
            lambda _=False, t=tab: self._close_tab(self.tabs.indexOf(t))
        )
        bar.setTabButton(idx, QTabBar.ButtonPosition.RightSide, btn)

    def _sync_tab_visibility(self) -> None:
        """根据可用宽度决定显示多少个标签，多余隐藏（缩到 MIN_W 即停）。"""
        bar = self.tabs.tabBar()
        n = self.tabs.count()
        if n == 0:
            return
        avail = bar.width() - AdaptiveTabBar.RESERVED
        if avail < AdaptiveTabBar.MIN_W:
            max_visible = 1
        else:
            max_visible = max(1, avail // AdaptiveTabBar.MIN_W)
        for i in range(n):
            bar.setTabVisible(i, i < max_visible)

    def _position_tab_plus(self, *_args) -> None:
        bar = self.tabs.tabBar()
        bar_pos = bar.mapTo(self.tabs, QPoint(0, 0))
        last_visible = -1
        for i in range(bar.count()):
            if bar.isTabVisible(i):
                last_visible = i
        if last_visible < 0:
            x_in_bar = 4
        else:
            x_in_bar = bar.tabRect(last_visible).right() + 6
        max_x_in_bar = bar.width() - self.tab_plus.width() - 4
        if max_x_in_bar < 0:
            max_x_in_bar = 0
        x_in_bar = min(x_in_bar, max_x_in_bar)
        x = bar_pos.x() + x_in_bar
        y = bar_pos.y() + (bar.height() - self.tab_plus.height()) // 2
        self.tab_plus.move(x, y)
        self.tab_plus.raise_()

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

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fs_log(
            f"resizeEvent {event.size().width()}x{event.size().height()}"
        )
        self.tabs.tabBar().update()
        self._sync_tab_visibility()
        self._elide_tab_titles()
        self._position_tab_plus()

    # ---------- 原生 Win32 全屏控制器 ----------
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

    def _hwnd(self):
        return wintypes.HWND(int(self.winId()))

    def _monitor_rect(self):
        """窗口所在显示器的物理像素矩形 (x, y, w, h)。"""
        hwnd = self._hwnd()
        mon = _user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if mon and _user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            r = info.rcMonitor
            return r.left, r.top, r.right - r.left, r.bottom - r.top
        scr = self.screen()
        if scr is None:
            from PyQt6.QtGui import QGuiApplication

            scr = QGuiApplication.primaryScreen()
        g = scr.geometry()
        return g.x(), g.y(), g.width(), g.height()

    def _log_qt_state(self, tag: str) -> None:
        self._fs_log(
            f"{tag}: qt windowState={int(self.windowState().value)} "
            f"isMaximized={self.isMaximized()} isFullScreen={self.isFullScreen()} "
            f"_is_fullscreen={self._is_fullscreen}"
        )

    def _native_enter_fullscreen(self) -> None:
        if not IS_WINDOWS:
            self.showFullScreen()
            self._is_fullscreen = True
            self._hide_chrome()
            return

        hwnd = self._hwnd()
        placement = _WINDOWPLACEMENT()
        placement.length = ctypes.sizeof(_WINDOWPLACEMENT)
        if not _user32.GetWindowPlacement(hwnd, ctypes.byref(placement)):
            self._fs_log("enter: GetWindowPlacement FAILED")
            return
        self._saved_placement = placement
        rn = placement.rcNormalPosition
        self._fs_log(
            f"enter: GetWindowPlacement ok showCmd={placement.showCmd} "
            f"rcNormal=({rn.left},{rn.top},{rn.right},{rn.bottom})"
        )

        style = _user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        if style is None:
            self._fs_log("enter: GetWindowLongPtrW FAILED")
            return
        self._saved_style = style
        strip = (
            WS_OVERLAPPEDWINDOW
            | WS_CAPTION
            | WS_THICKFRAME
            | WS_MINIMIZEBOX
            | WS_MAXIMIZEBOX
            | WS_SYSMENU
        )
        new_style = style & ~strip
        prev = _user32.SetWindowLongPtrW(hwnd, GWL_STYLE, new_style)
        self._fs_log(
            f"enter: SetWindowLongPtrW prev={_fmt_ptr(prev)} new={_fmt_ptr(new_style)}"
        )

        x, y, w, h = self._monitor_rect()
        ok = _user32.SetWindowPos(
            hwnd, HWND_TOP, x, y, w, h, SWP_FRAMECHANGED | SWP_NOZORDER
        )
        self._fs_log(
            f"enter: monitor=({x},{y},{w},{h}) SetWindowPos ok={bool(ok)}"
        )

        self._is_fullscreen = True
        self._hide_chrome()
        self._log_qt_state("enter done")

    def _native_exit_fullscreen(self) -> None:
        if not IS_WINDOWS:
            self.showNormal()
            self._is_fullscreen = False
            self._show_chrome()
            return

        hwnd = self._hwnd()
        if self._saved_style is not None:
            prev = _user32.SetWindowLongPtrW(hwnd, GWL_STYLE, self._saved_style)
            self._fs_log(f"exit: SetWindowLongPtrW restore prev={_fmt_ptr(prev)}")

        if self._saved_placement is not None:
            ok = _user32.SetWindowPlacement(hwnd, ctypes.byref(self._saved_placement))
            self._fs_log(
                f"exit: SetWindowPlacement ok={bool(ok)} "
                f"showCmd={self._saved_placement.showCmd}"
            )

        ok = _user32.SetWindowPos(
            hwnd,
            HWND_TOP,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )
        self._fs_log(f"exit: SetWindowPos refresh ok={bool(ok)}")

        self._saved_placement = None
        self._saved_style = None
        self._is_fullscreen = False
        self._show_chrome()
        self._log_qt_state("exit done")

    def enter_fullscreen(self, source: str = "video") -> None:
        """统一全屏入口。source: 'video' | 'hotkey'，仅用于标记。"""
        if self._is_fullscreen:
            return
        self._fullscreen_source = source
        self._fs_log(f"enter_fullscreen source={source}")
        self._native_enter_fullscreen()

    def exit_fullscreen(self) -> None:
        """统一退出全屏入口。"""
        if not self._is_fullscreen:
            return
        self._fs_log("exit_fullscreen")
        self._native_exit_fullscreen()

    def _toggle_fullscreen(self) -> None:
        if self._is_fullscreen:
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
        self.download_btn.setIcon(icons.icon("download", self.theme.text))
        self.download_btn.setText(f" {n}" if n else "")

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
        self._tab_full_titles[tab] = "新标签页"
        self._install_tab_close(tab)
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
        self._sync_tab_visibility()
        self._position_tab_plus()
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
        self._tab_full_titles.pop(w, None)
        w.deleteLater()
        self._sync_tab_visibility()
        self._position_tab_plus()

    def _current(self) -> Tab:
        return self.tabs.currentWidget()  # type: ignore[return-value]

    def _set_tab_title(self, tab: Tab, title: str) -> None:
        self._tab_full_titles[tab] = title or "新标签页"
        self._elide_tab_titles()
        self._position_tab_plus()

    def _elide_tab_titles(self) -> None:
        """按当前标签宽度用 QFontMetrics 右侧省略标题（跨平台稳定）。"""
        bar = self.tabs.tabBar()
        fm = QFontMetrics(bar.font())
        for i in range(self.tabs.count()):
            if not bar.isTabVisible(i):
                continue
            w = self.tabs.widget(i)
            full = self._tab_full_titles.get(w)
            if full is None:
                continue
            avail = bar.tabRect(i).width() - 40
            if avail < 16:
                avail = 16
            self.tabs.setTabText(i, fm.elidedText(full, Qt.TextElideMode.ElideRight, avail))

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
            self.bookmark_action.setIcon(icons.icon("star-fill", self.theme.accent))
        else:
            self.bookmark_action.setIcon(icons.icon("star", self.theme.text))

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