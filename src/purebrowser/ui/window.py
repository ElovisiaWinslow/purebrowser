import ctypes
import os
import sys
import time
from ctypes import wintypes
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QFontMetrics,
    QIcon,
    QKeySequence,
    QPalette,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWebEngineCore import (
    QWebEngineContextMenuRequest,
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineScript,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QTabBar,
    QToolBar,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from purebrowser.core.interceptor import Blocker
from purebrowser.core.locations import settings_file
from purebrowser.core.profile import build_profile
from purebrowser.core.settings import SEARCH_ENGINES, Settings
from purebrowser.data import bookmarks, history
from purebrowser.data import downloads_store
from purebrowser.data import favicons
from purebrowser.data import session
from purebrowser.pages.downloads import DownloadManager
from purebrowser.pages.newtab import NEWTAB_URL, display_url
from purebrowser.pages.pages import PureBrowserSchemeHandler
from purebrowser.data.storage import connect
from purebrowser.ui import icons
from purebrowser.ui import theme as theme_mod
from purebrowser.ui.freeze_overlay import FreezeOverlay
from purebrowser.ui.hud import FindHud, WheelZoomFilter, ZoomHud
from purebrowser.ui.context_menu import ContextMenu
from purebrowser.ui.context_menu import action as menu_action
from purebrowser.ui.context_menu import separator as menu_separator
from purebrowser.ui.dropdown import DropdownPanel
from purebrowser.ui.menu_rows import MenuRow
from purebrowser.ui.session_prompt import SessionPrompt
from purebrowser.ui.tab_area import TabArea
from purebrowser.ui.tab import FIND_SENTINEL, Tab, to_url
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
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    HWND_TOP = 0
    # 全屏时把窗口提到 topmost，盖住始终置顶的任务栏（否则第二次全屏起
    # 任务栏会从底部露出来，看起来像浅蓝色边框/圆角）。
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2

    MONITOR_DEFAULTTONEAREST = 0x00000002

    # --- 窗口消息 / 命中测试（方案 B：保留 WS_OVERLAPPEDWINDOW，自绘标题栏） ---
    WM_NCCALCSIZE = 0x0083
    WM_NCHITTEST = 0x0084
    WM_ERASEBKGND = 0x0014
    WM_ENTERSIZEMOVE = 0x0231
    WM_EXITSIZEMOVE = 0x0232
    WM_NCLBUTTONDOWN = 0x00A1

    HTCLIENT = 1
    HTCAPTION = 2
    HTMAXBUTTON = 8
    HTLEFT = 10
    HTRIGHT = 11
    HTTOP = 12
    HTTOPLEFT = 13
    HTTOPRIGHT = 14
    HTBOTTOM = 15
    HTBOTTOMLEFT = 16
    HTBOTTOMRIGHT = 17

    SW_MAXIMIZE = 3
    SW_MINIMIZE = 6
    SW_RESTORE = 9

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

    class _NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [
            ("rgrc", wintypes.RECT * 3),
            ("lppos", ctypes.c_void_p),
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
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

    _user32.IsZoomed.restype = wintypes.BOOL
    _user32.IsZoomed.argtypes = [wintypes.HWND]

    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]


def _fmt_ptr(value) -> str:
    if value is None:
        return "0x0(None)"
    return f"0x{int(value) & 0xFFFFFFFFFFFFFFFF:016X}"


# 页面缩放：步长 10%，合法范围 [0.25, 5.0]（越界 Qt 会静默忽略）。
ZOOM_MIN = 0.25
ZOOM_MAX = 5.0
ZOOM_STEP = 1.1

# Ctrl+F：注入脚本只在网页自身未处理（未 preventDefault）时打印暗号，
# 由 PurePage.javaScriptConsoleMessage 转成信号。这样 Overleaf 等自带 Ctrl+F
# 的页面优先，浏览器只在网页不用时才弹出查找条。
_FIND_HOOK_JS = (
    "(function(){"
    "if(window.__pbFindHooked)return;window.__pbFindHooked=true;"
    "window.addEventListener('keydown',function(e){"
    "if(!e.ctrlKey||e.shiftKey||e.altKey||e.metaKey)return;"
    "if(e.key!=='f'&&e.key!=='F')return;"
    "var ev=e;"
    "setTimeout(function(){"
    "if(!ev.defaultPrevented){try{console.log('" + FIND_SENTINEL + "');}catch(err){}}"
    "},0);"
    "},true);"
    "})();"
)


def _build_find_hook_script() -> QWebEngineScript:
    script = QWebEngineScript()
    script.setName("purebrowser-find-hook")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(True)
    script.setSourceCode(_FIND_HOOK_JS)
    return script


class _TitleButton(QToolButton):
    """标题条按钮：可在 hover 时切换图标（如关闭键变白）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._normal_icon = None
        self._hover_icon = None
        self._tip = ""

    def set_icons(self, normal, hover=None) -> None:
        self._normal_icon = normal
        self._hover_icon = hover
        self.setIcon(normal)

    def set_hovered(self, on: bool) -> None:
        """hover 由 `hovered` 动态属性驱动（QSS 不用 :hover），由轮询统一设置。"""
        if bool(self.property("hovered")) != bool(on):
            self.setProperty("hovered", bool(on))
            self.style().unpolish(self)
            self.style().polish(self)
        if on and self._hover_icon is not None:
            self.setIcon(self._hover_icon)
        elif not on and self._normal_icon is not None:
            self.setIcon(self._normal_icon)


class MainWindow(QMainWindow):
    def __init__(self, data_dir: Path):
        super().__init__()
        self.setWindowTitle("PureBrowser")
        # 上次窗口化时的几何（最大化期间也保持这个值，避免 normalGeometry 的边框误差累积）
        self._last_normal_rect = None
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        # 全屏控制器状态（唯一来源）。原生 API 改窗口后 Qt 不知情，
        # 因此 isFullScreen() 恒为 False，用这个标志替代。
        self._is_fullscreen = False
        self._fullscreen_source = None
        self._saved_placement = None
        self._saved_style = None
        # 最大化状态的唯一来源（不每次查 OS，避免 isMaximized/IsZoomed 失配）。
        self._maximized = False

        # 全屏时序调试探针（PUREBROWSER_FS_DEBUG=1 开启）
        self._fs_debug = bool(os.environ.get("PUREBROWSER_FS_DEBUG", "").strip())
        self._fs_t0 = None
        self._fs_probe_connected = False

        self.data_dir = Path(data_dir)
        self.conn = connect(self.data_dir / "purebrowser.db")
        self.settings = Settings(settings_file())
        self.theme = theme_mod.resolve_theme(self.settings.get("theme", "system"))
        self._tab_full_titles: dict = {}
        self._tab_urls: dict = {}

        netlog_env = os.environ.get("PUREBROWSER_NETLOG", "").strip()
        netlog_path = Path(netlog_env) if netlog_env else None

        self.blocker = Blocker(self.settings, netlog_path=netlog_path)
        self.profile: QWebEngineProfile = build_profile(self.data_dir, self.blocker)
        # Ctrl+F 网页优先：脚本注入在所有页面（含 iframe）最早期。
        self.profile.scripts().insert(_build_find_hook_script())
        self.scheme_handler = PureBrowserSchemeHandler(
            self.settings, self.conn, self.data_dir, self, theme=self.theme
        )
        self.profile.installUrlSchemeHandler(b"purebrowser", self.scheme_handler)

        self.downloads = DownloadManager(self.profile, self.settings, self.conn, self)
        self.downloads.changed.connect(self._refresh_download_button)
        # 上次会话遗留的进行中记录无法继续，标记为已中断；并裁剪历史到 200 条。
        downloads_store.mark_inprogress_as_interrupted(self.conn)
        downloads_store.prune(self.conn, 200)

        self.tabs = TabArea(self)
        bar = self.tabs.tabBar()
        bar.setExpanding(False)
        bar.setDrawBase(False)
        bar.setMinimumHeight(38)
        bar.setIconSize(QSize(16, 16))
        bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._sync_from_tab)

        # resize 时新露出的区域先用主题底色填充，避免 DWM 合成出现黑边。
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        mw_pal = self.palette()
        mw_pal.setColor(QPalette.ColorRole.Window, QColor(self.theme.window))
        self.setPalette(mw_pal)

        # 顶行（窗口最顶部，38px）：标签栏 + 窗口控制键同行（B-2.2b）。
        self.top_row = QWidget(self)
        self.top_row.setObjectName("topRow")
        self.top_row.setFixedHeight(38)
        self.top_row.setStyleSheet(
            f"#topRow {{ background: {self.theme.chrome};"
            f" border-bottom: 1px solid {self.theme.border}; }}"
        )
        top_lay = QHBoxLayout(self.top_row)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(0)
        top_lay.addWidget(bar, 1)
        self.win_min = self._make_title_button("minimize", "最小化", self.showMinimized)
        self.win_max = self._make_title_button("maximize", "最大化", self._toggle_maximize)
        self.win_close = self._make_title_button("close", "关闭", self.close, close=True)
        top_lay.addWidget(self.win_min)
        top_lay.addWidget(self.win_max)
        top_lay.addWidget(self.win_close)

        # 中央容器：top_row / toolbar / 内容 stack（自上而下）。
        self._build_toolbar()
        central = QWidget(self)
        central_lay = QVBoxLayout(central)
        central_lay.setContentsMargins(0, 0, 0, 0)
        central_lay.setSpacing(0)
        central_lay.addWidget(self.top_row)
        central_lay.addWidget(self.toolbar)
        central_lay.addWidget(self.tabs.stack(), 1)
        self.setCentralWidget(central)

        # 拖动 resize 期间的冻结帧：覆盖内容 stack（B-2.2b 改父到 stack）。
        self._freeze_overlay = FreezeOverlay(self.tabs.stack())

        self._build_statusbar()
        self._build_zoom_hud()
        self._build_find_hud()
        self._build_dropdowns()
        self._build_tab_plus()

        # 三键 hover：轮询光标统一驱动（非客户区 max 收不到 Qt enter/leave）。
        self._hover_btn = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(60)
        self._hover_timer.timeout.connect(self._poll_caption_hover)
        self._hover_timer.start()

        self._install_shortcuts()

        # 最近关闭标签栈（内存，仅记用户主动关闭的标签）与会话 debounce 定时器。
        self._closed_tabs: list = []
        self._session_timer = QTimer(self)
        self._session_timer.setSingleShot(True)
        self._session_timer.setInterval(800)
        self._session_timer.timeout.connect(self._save_session)

        # 会话恢复：读一次快照，决定是否需要弹"恢复会话"提示；先开一个占位
        # newtab（首屏与测试都依赖 current() 有标签）。
        self._saved_session = session.load(self.data_dir)
        self._pending_restore = self._compute_pending_restore(self._saved_session)
        self._prompt_card = None
        self._start_maximized = False
        self._start_rect = None
        self._apply_startup_geometry(self._saved_session.get("window") or {})
        self.new_tab(NEWTAB_URL)

        self._relayout_tabs()
        self._update_max_icon()

    # ---------- session startup ----------
    def _compute_pending_restore(self, data: dict):
        """返回 (tabs, active) 供弹窗恢复；不需要恢复时返回 None。"""
        if not self.settings.get("restore_session", True):
            return None
        kept = []
        for i, t in enumerate(data.get("tabs", []) or []):
            url = (t.get("url") or "").strip()
            if not url or url.startswith("purebrowser://newtab"):
                continue
            kept.append((i, {"url": url, "title": t.get("title", "")}))
        if not kept:
            return None
        tabs = [t for _i, t in kept]
        active = data.get("active", -1)
        target = len(tabs) - 1
        for pos, (orig, _t) in enumerate(kept):
            if orig == active:
                target = pos
                break
        return tabs, max(0, min(int(target), len(tabs) - 1))

    def _apply_startup_geometry(self, win_state: dict) -> None:
        """解析上次的窗口状态：仅记录，实际在 start() 里 apply（见下）。

        自愈：早期版本在最大化时会把最大化几何写进 window.w/h，导致保存的"窗口化
        尺寸"= 工作区尺寸，于是点"还原"看着没变。这里若 maximized 且尺寸≈工作区，
        判为坏值，改用默认窗口矩形。
        """
        self._start_maximized = bool(win_state.get("maximized"))
        rect = None
        try:
            w = int(win_state.get("w") or 0)
            h = int(win_state.get("h") or 0)
            x = int(win_state.get("x"))
            y = int(win_state.get("y"))
            if w > 0 and h > 0:
                rect = QRect(x, y, w, h)
        except (TypeError, ValueError):
            rect = None
        if rect is not None and self._start_maximized and self._looks_like_workarea(rect):
            rect = None
        self._start_rect = rect if rect is not None else self._default_window_rect()

    @staticmethod
    def _looks_like_workarea(rect: QRect) -> bool:
        from PyQt6.QtGui import QGuiApplication

        for screen in QGuiApplication.screens():
            g = screen.availableGeometry()
            if rect.width() >= g.width() * 0.98 and rect.height() >= g.height() * 0.98:
                return True
        return False

    @staticmethod
    def _default_window_rect() -> QRect:
        """默认窗口化矩形：1200×800（受工作区限制）并居中。"""
        from PyQt6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, 1200, 800)
        g = screen.availableGeometry()
        w = min(1200, max(400, g.width() - 80))
        h = min(800, max(300, g.height() - 80))
        x = g.left() + (g.width() - w) // 2
        y = g.top() + (g.height() - h) // 2
        return QRect(x, y, w, h)

    def _clamp_start_rect(self) -> None:
        """确保恢复的窗口矩形与当前某个屏幕的工作区相交（换了显示器时兜底）。"""
        from PyQt6.QtGui import QGuiApplication

        rect = self._start_rect
        if rect is None:
            self._start_rect = self._default_window_rect()
            rect = self._start_rect
        for screen in QGuiApplication.screens():
            if screen.availableGeometry().intersects(rect):
                return
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        g = screen.availableGeometry()
        self._start_rect = QRect(g.left() + 60, g.top() + 60, rect.width(), rect.height())

    def start(self) -> None:
        """应用启动入口：按上次状态显示窗口，必要时弹出恢复会话提示。

        注意：setGeometry 必须在 show() 之后再落一次——窗口首次显示时 Qt/Windows
        会按窗口边框做一次尺寸膨胀（本窗口自绘无边框，膨胀会污染下次保存的尺寸）。
        """
        self._clamp_start_rect()
        if self._start_rect is not None:
            self.setGeometry(self._start_rect)
        self.show()
        self._ensure_state_probe()
        if self._start_rect is not None:
            self.setGeometry(self._start_rect)
        self._maximized = bool(self._start_maximized)
        if self._maximized:
            self.showMaximized()
        # 显式刷成启动状态；下一拍按真实 IsZoomed 对账一次（外部/系统态）。
        self._set_max_icon(self._maximized)
        QTimer.singleShot(0, self._update_max_icon)
        if self._pending_restore:
            QTimer.singleShot(0, self._ask_restore)


    def _ask_restore(self) -> None:
        if not self._pending_restore:
            return
        tabs, active = self._pending_restore
        card = SessionPrompt(self.theme, self.tabs.stack())
        card.set_count(len(tabs))
        card.restore.connect(lambda: self._resolve_restore(True))
        card.skip.connect(lambda: self._resolve_restore(False))
        self._prompt_card = card
        card.show_card()

    def _resolve_restore(self, restore: bool) -> None:
        pending = self._pending_restore
        self._pending_restore = None
        if self._prompt_card is not None:
            self._prompt_card.hide()
            self._prompt_card = None
        if restore and pending:
            self._load_tabs(pending[0], pending[1])
        self._schedule_session_save()

    def _load_tabs(self, tabs: list, active: int) -> None:
        """把上次会话的标签页装回来；复用占位 newtab，避免"最后一个标签"限制。"""
        urls = [t.get("url") for t in tabs if t.get("url")]
        if not urls:
            return
        rest = urls
        if self.tabs.count() == 1:
            cur = self._current()
            if isinstance(cur, Tab) and self._tab_urls.get(cur, "").startswith(
                "purebrowser://newtab"
            ):
                cur.load(QUrl(urls[0]))
                self._tab_urls[cur] = urls[0]
                rest = urls[1:]
        for u in rest:
            self.new_tab(QUrl(u))
        target = active if 0 <= active < len(urls) else len(urls) - 1
        self.tabs.setCurrentIndex(max(0, min(target, self.tabs.count() - 1)))

    # ---------- UI ----------
    def _build_toolbar(self) -> None:
        self.toolbar = QToolBar("Main", self)
        self.toolbar.setMovable(False)
        self.toolbar.setIconSize(QSize(18, 18))
        self.toolbar.setFixedHeight(56)

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
        self.history_btn.clicked.connect(
            lambda: self._toggle_dropdown("history", self.history_btn)
        )
        self.toolbar.addWidget(self.history_btn)

        self.bookmarks_btn = QToolButton(self)
        self.bookmarks_btn.setIcon(icons.icon("bookmark", self.theme.text))
        self.bookmarks_btn.setToolTip("书签")
        self.bookmarks_btn.clicked.connect(
            lambda: self._toggle_dropdown("bookmarks", self.bookmarks_btn)
        )
        self.toolbar.addWidget(self.bookmarks_btn)

        self.download_btn = QToolButton(self)
        self.download_btn.setIcon(icons.icon("download", self.theme.text))
        self.download_btn.setToolTip("下载")
        self.download_btn.clicked.connect(
            lambda: self._toggle_dropdown("download", self.download_btn)
        )
        self.toolbar.addWidget(self.download_btn)

        # 下载中角标：红底白字数量，浮在工具栏上、叠在按钮右上角（子控件会被
        # 按钮矩形裁剪，故挂在工具栏而非按钮上）。
        self.dl_badge = QLabel(self.toolbar)
        self.dl_badge.setObjectName("dlBadge")
        self.dl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dl_badge.setFixedSize(15, 15)
        self.dl_badge.setStyleSheet(
            f"#dlBadge {{ background: {self.theme.danger}; color: #FFFFFF;"
            " border-radius: 7px; font-size: 9px; font-weight: 600; }"
        )
        self.dl_badge.setVisible(False)
        self.download_btn.installEventFilter(self)
        self.toolbar.installEventFilter(self)

        settings_action = self.toolbar.addAction(icons.icon("settings", self.theme.text), "")
        settings_action.setToolTip("设置")
        settings_action.triggered.connect(self._open_settings)

        # 不用 QGraphicsDropShadowEffect：带阴影的工具栏每次重绘要重新离屏渲染
        # + 高斯模糊（实测 3.4ms vs 无阴影 0.44ms，8 倍），会与视频合成抢 GUI 线程。
        # 阴影由 QSS 边框替代。

    def _build_dropdowns(self) -> None:
        """历史/书签/下载共用的自绘可滚动下拉面板（非 QMenu，见 ui/dropdown.py）。"""
        self._dropdowns = {
            "history": DropdownPanel(self.theme),
            "bookmarks": DropdownPanel(self.theme),
            "download": DropdownPanel(self.theme),
        }
        self._dl_live_timer = QTimer(self)
        self._dl_live_timer.setInterval(200)
        self._dl_live_timer.timeout.connect(self._update_download_panel)

    def _toggle_dropdown(self, kind: str, anchor) -> None:
        panel = self._dropdowns[kind]
        if panel.isVisible():
            panel.hide()
            if kind == "download":
                self._dl_live_timer.stop()
            return
        if kind == "history":
            self._fill_history_panel(panel)
        elif kind == "bookmarks":
            self._fill_bookmarks_panel(panel)
        elif kind == "download":
            self._fill_download_panel(panel)
        panel.open_below(anchor)
        if kind == "download":
            self._dl_live_timer.start()

    def _position_download_badge(self) -> None:
        if not hasattr(self, "dl_badge"):
            return
        b = self.dl_badge
        tl = self.download_btn.mapTo(self.toolbar, QPoint(0, 0))
        x = tl.x() + self.download_btn.width() - b.width() + 3
        y = max(0, tl.y() - 1)
        b.move(x, y)
        b.raise_()

    def _build_find_hud(self) -> None:
        """查找条改为右上角浮层（复用一个 FloatingHud），不再挤动页面布局。"""
        self.find_hud = FindHud(self.tabs.stack())
        self.find_hud.text_changed.connect(self._on_find_text_changed)
        self.find_hud.next_requested.connect(self._find_next)
        self.find_hud.prev_requested.connect(self._find_prev)
        self.find_hud.close_requested.connect(self._hide_find_bar)

    def _show_find_bar(self) -> None:
        self.find_hud.open()
        text = self.find_hud.input.text()
        if text:
            self._on_find_text_changed(text)

    def _on_shortcut_unhandled(self, tab, action: str) -> None:
        """注入脚本报告网页未处理 Ctrl+F：仅当前标签打开查找条。"""
        if action != "find":
            return
        if tab is not self.tabs.currentWidget():
            return
        self._show_find_bar()

    def _hide_find_bar(self) -> None:
        if not self.find_hud.isVisible():
            return
        self.find_hud.hide()
        self.find_hud.input.clear()
        page = self._current().view.page()
        if page is not None:
            page.findText("")
        self.find_hud.set_count("0/0")

    def _on_find_text_changed(self, text: str) -> None:
        page = self._current().view.page()
        if page is None:
            return
        if not text:
            page.findText("")
            self.find_hud.set_count("0/0")
            return
        page.findText(text)

    def _find_next(self) -> None:
        text = self.find_hud.input.text()
        if not text:
            return
        page = self._current().view.page()
        if page is not None:
            page.findText(text)

    def _find_prev(self) -> None:
        text = self.find_hud.input.text()
        if not text:
            return
        page = self._current().view.page()
        if page is not None:
            page.findText(text, QWebEnginePage.FindFlag.FindBackward)

    def _on_find_result(self, result) -> None:
        total = result.numberOfMatches()
        active = result.activeMatch()
        self.find_hud.set_count("0/0" if total <= 0 else f"{active}/{total}")

    def _handle_escape(self) -> None:
        """Esc 优先级：先关查找浮层，否则走原有退出全屏逻辑。"""
        if self.find_hud.isVisible():
            self._hide_find_bar()
            return
        self._exit_fullscreen()

    def _build_statusbar(self) -> None:
        self.progress = QProgressBar(self)
        self.progress.setMaximumWidth(160)
        self.progress.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress)

    def _build_zoom_hud(self) -> None:
        # 浮层挂在内容 stack 上：全屏时 stack 仍在，缩放指示可见。
        self.zoom_hud = ZoomHud(self.tabs.stack())
        self.zoom_hud.step_requested.connect(self._zoom_step)
        self.zoom_hud.percent_requested.connect(self._zoom_to_percent)
        self.zoom_hud.reset_requested.connect(self._zoom_reset)
        # Ctrl+滚轮桥接到 _zoom_step。滚轮事件落点是 view 的 focusProxy，
        # 但 focusProxy 在 view 首次显示后才存在且可能被替换，故按需安装。
        self._wheel_filter = WheelZoomFilter(self._zoom_step)
        self._wheel_targets: set = set()

    def _ensure_wheel_filter(self, view) -> None:
        fp = view.focusProxy()
        if fp is None or fp in self._wheel_targets:
            return
        fp.installEventFilter(self._wheel_filter)
        self._wheel_targets.add(fp)

    def eventFilter(self, obj, event):
        # view 首次显示/打磨后 focusProxy 才可用：此时挂上滚轮过滤器。
        et = event.type()
        if et in (QEvent.Type.Show, QEvent.Type.Polish):
            self._ensure_wheel_filter(obj)
        elif et in (QEvent.Type.Resize, QEvent.Type.Move, QEvent.Type.LayoutRequest):
            if obj is getattr(self, "toolbar", None) or obj is getattr(self, "download_btn", None):
                self._position_download_badge()
        return super().eventFilter(obj, event)

    # ---------- 页面缩放 ----------
    def _site_zoom(self) -> dict:
        data = self.settings.get("site_zoom", {})
        return dict(data) if isinstance(data, dict) else {}

    @staticmethod
    def _zoom_host(url: QUrl) -> str:
        return (url.host() or "").lower()

    @staticmethod
    def _clamp_zoom(factor: float) -> float:
        return max(ZOOM_MIN, min(ZOOM_MAX, factor))

    def _apply_site_zoom(self, view, url: QUrl) -> None:
        host = self._zoom_host(url)
        factor = 1.0
        if host:
            try:
                factor = float(self._site_zoom().get(host, 1.0))
            except (TypeError, ValueError):
                factor = 1.0
        factor = self._clamp_zoom(factor)
        if abs(view.zoomFactor() - factor) > 1e-6:
            view.setZoomFactor(factor)

    def _persist_site_zoom(self, url: QUrl, factor: float) -> None:
        host = self._zoom_host(url)
        if not host:
            return
        data = self._site_zoom()
        data[host] = factor
        self.settings.set("site_zoom", data)

    def _zoom_step(self, direction: int) -> None:
        view = self._current().view
        factor = view.zoomFactor() * (ZOOM_STEP if direction > 0 else 1.0 / ZOOM_STEP)
        factor = self._clamp_zoom(round(factor, 3))
        view.setZoomFactor(factor)
        self._persist_site_zoom(view.url(), factor)
        self.zoom_hud.show_percent(factor, 2000)

    def _zoom_to_percent(self, percent: int) -> None:
        if percent == 100:
            self._zoom_reset()
            return
        factor = self._clamp_zoom(round(percent / 100.0, 3))
        view = self._current().view
        view.setZoomFactor(factor)
        self._persist_site_zoom(view.url(), factor)
        self.zoom_hud.show_percent(factor, 2000)

    def _zoom_reset(self) -> None:
        view = self._current().view
        view.setZoomFactor(1.0)
        host = self._zoom_host(view.url())
        if host:
            data = self._site_zoom()
            if host in data:
                del data[host]
                self.settings.set("site_zoom", data)
        self.zoom_hud.show_percent(1.0, 2000)

    def _make_title_button(self, icon_name, tip, slot, close=False) -> _TitleButton:
        size = 10
        btn = _TitleButton(self.top_row)
        btn.setObjectName("winClose" if close else "winBtn")
        normal = icons.icon(icon_name, self.theme.text, size)
        hover = icons.icon(icon_name, "#FFFFFF", size) if close else None
        btn.set_icons(normal, hover)
        btn.setIconSize(QSize(size, size))
        btn.setFixedSize(46, 38)
        btn._tip = tip  # tooltip 由 MainWindow 轮询自管（Qt tooltip 会在非客户区错显）
        btn.clicked.connect(slot)
        return btn

    def _set_max_icon(self, maximized: bool) -> None:
        if not hasattr(self, "win_max"):
            return
        name = "restore" if maximized else "maximize"
        self.win_max.set_icons(icons.icon(name, self.theme.text, 10), None)
        self.win_max._tip = "还原" if maximized else "最大化"

    def _is_zoomed(self) -> bool:
        """窗口是否最大化——以原生 IsZoomed 为准。

        本窗口自绘无边框 + 原生 ShowWindow，Qt 的 isMaximized() 偶尔与实际
        OS 状态不一致，会导致"图标显示还原、点击却当没最大化又去最大化"。
        """
        if IS_WINDOWS:
            try:
                return bool(_user32.IsZoomed(self._hwnd()))
            except Exception:
                pass
        return self.isMaximized()

    def _update_max_icon(self) -> None:
        # 外部改动（Win+↑/贴靠/系统还原等）时用 IsZoomed 校正一次 flag。
        self._maximized = self._is_zoomed()
        self._set_max_icon(self._maximized)

    def _toggle_maximize(self) -> None:
        # 只翻转自维护状态，不查 OS：点击行为与图标永远一致。
        self._maximized = not self._maximized
        if IS_WINDOWS:
            hwnd = self._hwnd()
            _user32.ShowWindow(
                hwnd, SW_MAXIMIZE if self._maximized else SW_RESTORE
            )
        elif self._maximized:
            self.showMaximized()
        else:
            self.showNormal()
        self._set_max_icon(self._maximized)
        self._fs_log(f"toggle_maximize -> _maximized={self._maximized}")

    def _build_tab_plus(self) -> None:
        """+ 按钮是 top_row 的子控件，动态跟随最后一个标签（带上限）。"""
        self.tab_plus = QToolButton(self.top_row)
        self.tab_plus.setObjectName("tabPlus")
        self.tab_plus.setText("")
        self.tab_plus.setIcon(icons.icon("plus", self.theme.subtext, 16))
        self.tab_plus.setIconSize(QSize(16, 16))
        self.tab_plus.setToolTip("新标签页")
        self.tab_plus.setFixedSize(28, 28)
        self.tab_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_plus.clicked.connect(lambda: self.new_tab(NEWTAB_URL))
        bar = self.tabs.tabBar()
        bar.tabMoved.connect(self._relayout_tabs)
        bar.currentChanged.connect(self._relayout_tabs)
        bar.set_relayout_callback(self._relayout_tabs)
        self._relayout_tabs()

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
        """滑动可见窗口：可见标签数恒 = max_visible，且窗口始终包含当前标签。

        - 当前标签永不被隐藏（避免 QTabWidget/stack 自动切走激活标签）。
        - 可见标签总宽 = max_visible*MIN_W ≤ avail，保证 + 永远不压标签。
        """
        bar = self.tabs.tabBar()
        n = self.tabs.count()
        if n == 0:
            return
        # 标签栏不可见时（如全屏隐藏）不重算，避免用宽度 0 误判 max_visible。
        if not bar.isVisible():
            return
        avail = bar.width() - AdaptiveTabBar.RESERVED
        if avail < AdaptiveTabBar.MIN_W:
            max_visible = 1
        else:
            max_visible = max(1, avail // AdaptiveTabBar.MIN_W)
        if n <= max_visible:
            for i in range(n):
                bar.setTabVisible(i, True)
            return
        current = self.tabs.currentIndex()
        start = current - max_visible + 1
        if start < 0:
            start = 0
        if start > n - max_visible:
            start = n - max_visible
        end = start + max_visible
        for i in range(n):
            bar.setTabVisible(i, start <= i < end)

    def _position_tab_plus(self, *_args) -> None:
        bar = self.tabs.tabBar()
        bar_pos = bar.mapTo(self.top_row, QPoint(0, 0))
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

    def _relayout_tabs(self, *_args) -> None:
        """统一入口：立即重排一次，并在下一轮事件循环再算一次（兜住布局滞后一帧）。"""
        self._relayout_immediate()
        if not getattr(self, "_relayout_pending", False):
            self._relayout_pending = True
            QTimer.singleShot(0, self._relayout_deferred)

    def _relayout_immediate(self) -> None:
        if getattr(self, "_relayout_guard", False):
            return
        self._relayout_guard = True
        try:
            self._sync_tab_visibility()
            self._elide_tab_titles()
            self._position_tab_plus()
        finally:
            self._relayout_guard = False

    def _relayout_deferred(self) -> None:
        self._relayout_pending = False
        self._relayout_immediate()

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(
            lambda: self.new_tab(NEWTAB_URL)
        )
        QShortcut(QKeySequence("Ctrl+Shift+T"), self).activated.connect(
            self._reopen_closed_tab
        )
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(
            lambda: self._close_tab(self.tabs.currentIndex())
        )
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self._focus_url_bar)
        # Ctrl+F 不再用 QShortcut 抢占：交给注入脚本判断网页是否已处理，
        # 未处理时经 shortcut_unhandled 信号回到 _show_find_bar（见 new_tab）。
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
            lambda: self._toggle_dropdown("bookmarks", self.bookmarks_btn)
        )
        QShortcut(QKeySequence("Ctrl+J"), self).activated.connect(
            lambda: self._toggle_dropdown("download", self.download_btn)
        )
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._handle_escape)
        QShortcut(QKeySequence("Ctrl++"), self).activated.connect(
            lambda: self._zoom_step(1)
        )
        QShortcut(QKeySequence("Ctrl+="), self).activated.connect(
            lambda: self._zoom_step(1)
        )
        QShortcut(QKeySequence("Ctrl+Shift+="), self).activated.connect(
            lambda: self._zoom_step(1)
        )
        QShortcut(QKeySequence("Ctrl+-"), self).activated.connect(
            lambda: self._zoom_step(-1)
        )
        QShortcut(QKeySequence("Ctrl+Shift+-"), self).activated.connect(
            lambda: self._zoom_step(-1)
        )
        QShortcut(QKeySequence("Ctrl+0"), self).activated.connect(self._zoom_reset)

    def _focus_url_bar(self) -> None:
        self.url_bar.setFocus()
        self.url_bar.selectAll()

    # ---------- 全屏时序调试探针（PUREBROWSER_FS_DEBUG=1 开启） ----------
    def _ensure_state_probe(self) -> None:
        """连接 windowStateChanged（幂等）。首帧 windowHandle() 可能还没就绪，
        故 showEvent 与 start() 里都会尝试一次。"""
        if self._fs_probe_connected:
            return
        wh = self.windowHandle()
        if wh is None:
            return
        wh.windowStateChanged.connect(self._on_window_state_changed)
        self._fs_probe_connected = True
        self._fs_log("windowStateChanged probe connected")

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._ensure_state_probe()

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
        # 本窗口是自绘无边框 + 原生 ShowWindow，Qt 发来的 state 可能是"激活"
        # 类的过时事件（不带 Maximized），直接据此刷图标会把已最大化的窗口刷回
        # "最大化"。故延到下一个事件循环，按真实 isMaximized() 对账。
        QTimer.singleShot(0, self._update_max_icon)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fs_log(
            f"resizeEvent {event.size().width()}x{event.size().height()}"
        )
        # 用原生 IsZoomed 判定：最大化时 isMaximized() 会滞后一拍，会把最大化
        # 几何写进 _last_normal_rect，导致保存出去的"窗口化尺寸"= 工作区尺寸。
        if not self._is_zoomed() and not self._is_fullscreen:
            self._last_normal_rect = self.geometry()
        self.tabs.tabBar().update()
        self._relayout_tabs()
        if getattr(self, "_freeze_overlay", None) is not None and self._freeze_overlay.isVisible():
            self._sync_overlay_geometry()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if not self._is_zoomed() and not self._is_fullscreen:
            self._last_normal_rect = self.geometry()

    # ---------- 原生 Win32 全屏控制器 ----------
    def nativeEvent(self, eventType, message):
        """方案 B：保留 WS_OVERLAPPEDWINDOW，用消息钩子实现自绘标题栏。

        注意：本回调由 C++ 直接调用，任何 Python 异常逃逸都会触发
        0xC000041D（fatal user callback exception）。因此这里整体 try/except，
        且绝不调用 super().nativeEvent（PyQt6 下并非安全默认实现）。
        """
        try:
            if IS_WINDOWS and bytes(eventType) == b"windows_generic_MSG":
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_NCCALCSIZE and msg.wParam:
                    # 客户区铺满整个窗口 → 去掉系统 caption；最大化时对齐工作区。
                    self._adjust_maximized_client(msg)
                    return True, 0
                if msg.message == WM_ERASEBKGND:
                    return True, 1  # 由 Qt 负责重绘背景，禁止系统擦除
                if msg.message == WM_ENTERSIZEMOVE:
                    # 用户开始拖动/调整：窗口必然回到窗口化，同步状态与图标。
                    self._maximized = False
                    self._set_max_icon(False)
                    self._freeze_begin()
                    return True, 0
                if msg.message == WM_EXITSIZEMOVE:
                    self._freeze_end()
                    return True, 0
                if msg.message == WM_NCHITTEST:
                    return True, self._native_hit_test(msg)
        except Exception:
            pass
        return False, 0

    def _adjust_maximized_client(self, msg) -> None:
        """把客户区对齐正确的矩形。

        - 全屏：对齐整个显示器（rcMonitor）。全屏时窗口仍带 WS_MAXIMIZE，
          IsZoomed 为真，若按工作区裁就会在底部露出任务栏（浅蓝色边角）。
        - 最大化（非全屏）：对齐工作区，消除系统 resize 边框对标签栏顶部 /
          状态栏底部的 11px 遮挡（SM_CXSIZEFRAME+CXPADDEDBORDER）。
        """
        if not IS_WINDOWS:
            return
        if getattr(self, "_is_fullscreen", False):
            target = "monitor"
        elif _user32.IsZoomed(msg.hWnd):
            target = "work"
        else:
            return
        mon = _user32.MonitorFromWindow(msg.hWnd, MONITOR_DEFAULTTONEAREST)
        if not mon:
            return
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not _user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return
        params = ctypes.cast(
            ctypes.c_void_p(msg.lParam), ctypes.POINTER(_NCCALCSIZE_PARAMS)
        ).contents
        rect = info.rcMonitor if target == "monitor" else info.rcWork
        params.rgrc[0].left = rect.left
        params.rgrc[0].top = rect.top
        params.rgrc[0].right = rect.right
        params.rgrc[0].bottom = rect.bottom

    def _poll_caption_hover(self) -> None:
        """轮询光标统一驱动三键 hover（不依赖 Qt enter/leave，规避 HTMAXBUTTON
        非客户区导致的残留 hover/tooltip）。"""
        pos = self.mapFromGlobal(QCursor.pos())
        target = None
        for btn in (
            getattr(self, "win_min", None),
            getattr(self, "win_max", None),
            getattr(self, "win_close", None),
        ):
            if btn is None or not btn.isVisible():
                continue
            tl = btn.mapTo(self, QPoint(0, 0))
            if QRect(tl, btn.size()).contains(pos):
                target = btn
                break
        if target is self._hover_btn:
            return
        if self._hover_btn is not None:
            self._hover_btn.set_hovered(False)
        if target is not None:
            target.set_hovered(True)
        self._hover_btn = target
        if target is not None and getattr(target, "_tip", ""):
            QToolTip.showText(QCursor.pos(), target._tip, target)
        else:
            QToolTip.hideText()

    def _freeze_begin(self) -> None:
        """用户开始拖动/调整窗口：抓当前 WebEngine 画面，用 overlay 拉伸显示。"""
        if self._is_fullscreen:
            return
        if self.tabs.count() == 0:
            return
        view = self._current().view
        if view is None or view.width() <= 0 or view.height() <= 0:
            return
        pixmap = view.grab()
        self._freeze_overlay.setParent(self.tabs.stack())
        self._sync_overlay_geometry()
        self._freeze_overlay.set_frame(pixmap)
        self._freeze_overlay.show()
        self._freeze_overlay.raise_()

    def _freeze_end(self) -> None:
        """用户松手：隐藏 overlay，恢复 WebEngine 实时渲染。"""
        self._freeze_overlay.hide()
        self._freeze_overlay.clear_frame()

    def _sync_overlay_geometry(self) -> None:
        # overlay 父控件是内容 stack，几何即 stack 的完整矩形。
        st = self.tabs.stack()
        self._freeze_overlay.setGeometry(0, 0, st.width(), st.height())

    def _native_hit_test(self, msg) -> int:
        """屏幕物理坐标 → 窗口本地逻辑坐标后判定命中区（含 150% DPI 换算）。"""
        # 全屏下不做缩放/拖动/Snap：所有命中交给页面（视频控制栏等仍可交互）。
        if self._is_fullscreen:
            return HTCLIENT
        gx = ctypes.c_short(msg.lParam & 0xFFFF).value
        gy = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
        wh = self.windowHandle()
        dpr = wh.devicePixelRatio() if wh is not None else 1.0
        if dpr <= 0:
            dpr = 1.0
        local = self.mapFromGlobal(
            QPoint(int(round(gx / dpr)), int(round(gy / dpr)))
        )
        x, y = local.x(), local.y()
        w, h = self.width(), self.height()
        b = 8  # 缩放边框（逻辑像素）
        left = x < b
        right = x >= w - b
        top = y < b
        bottom = y >= h - b
        if top and left:
            return HTTOPLEFT
        if top and right:
            return HTTOPRIGHT
        if bottom and left:
            return HTBOTTOMLEFT
        if bottom and right:
            return HTBOTTOMRIGHT
        if left:
            return HTLEFT
        if right:
            return HTRIGHT
        if top:
            return HTTOP
        if bottom:
            return HTBOTTOM
        # 窗口控制键：交给 Qt 处理点击（全部 HTCLIENT）。
        # 注意：max 键不再返回 HTMAXBUTTON——那样点击会由 Win11 系统接管，
        # 我们的状态机拿不到点击。这里让 Qt 按钮收点击，_toggle_maximize 全权控制。
        for btn in (
            getattr(self, "win_min", None),
            getattr(self, "win_max", None),
            getattr(self, "win_close", None),
        ):
            if btn is None or not btn.isVisible():
                continue
            tl = btn.mapTo(self, QPoint(0, 0))
            if QRect(tl, btn.size()).contains(local):
                return HTCLIENT
        # 顶行空白 → HTCAPTION（可拖动窗口 / 双击最大化）；
        # 可见标签矩形、+ 按钮除外。标签矩形实时计算，不缓存。
        tr = getattr(self, "top_row", None)
        if tr is not None and tr.isVisible() and tr.geometry().contains(local):
            pt = tr.mapFrom(self, local)
            bar = self.tabs.tabBar()
            bar_pt = bar.mapFrom(tr, pt)
            for i in range(bar.count()):
                if bar.isTabVisible(i) and bar.tabRect(i).contains(bar_pt):
                    return HTCLIENT
            plus = getattr(self, "tab_plus", None)
            if plus is not None and plus.isVisible() and plus.geometry().contains(pt):
                return HTCLIENT
            return HTCAPTION
        return HTCLIENT

    def _hide_chrome(self) -> None:
        self.top_row.hide()
        self.toolbar.hide()
        self.statusBar().hide()

    def _show_chrome(self) -> None:
        self.top_row.show()
        self.toolbar.show()
        self.statusBar().show()

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

        # 先置全屏标志：下面 SetWindowPos 会触发 WM_NCCALCSIZE，
        # _adjust_maximized_client 必须知道此时是全屏，客户区才会取整块显示器
        # （否则仍带 WS_MAXIMIZE 会按工作区裁，底部漏出任务栏）。
        self._is_fullscreen = True

        x, y, w, h = self._monitor_rect()
        ok = _user32.SetWindowPos(
            hwnd, wintypes.HWND(HWND_TOPMOST), x, y, w, h, SWP_FRAMECHANGED
        )
        _user32.SetForegroundWindow(hwnd)
        self._fs_log(
            f"enter: monitor=({x},{y},{w},{h}) SetWindowPos(topmost) ok={bool(ok)}"
        )

        self._hide_chrome()
        self._log_qt_state("enter done")

    def _native_exit_fullscreen(self) -> None:
        if not IS_WINDOWS:
            self.showNormal()
            self._is_fullscreen = False
            self._show_chrome()
            return

        # 先清全屏标志：恢复最大化时 NCCALCSIZE 要按工作区对齐（而非整块显示器）。
        self._is_fullscreen = False

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

        # 取消 topmost，防止退出全屏后还压在其他窗口之上。
        ok = _user32.SetWindowPos(
            hwnd,
            wintypes.HWND(HWND_NOTOPMOST),
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
        )
        self._fs_log(f"exit: SetWindowPos refresh ok={bool(ok)}")

        self._saved_placement = None
        self._saved_style = None
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

    # ---------- dropdown rows ----------
    def _host_icon(self, host: str):
        if host:
            pixmap = favicons.get(self.conn, host)
            if pixmap is not None:
                return pixmap
        return self._globe_icon()

    def _make_row(self, *, title, subtitle="", icon=None, url=None, kind=None,
                  key=None, buttons=None, path=None, rec=None, retry_url=None,
                  progress=None):
        row = MenuRow(
            self.theme,
            title,
            subtitle=subtitle,
            icon=icon,
            dim=(url is None),
            buttons=buttons,
            deletable=(buttons is None and kind in ("history", "bookmark")),
            progress=progress,
        )
        row._meta = {"kind": kind, "key": key, "url": url, "path": path,
                     "rec": rec, "retry_url": retry_url}
        row.clicked.connect(self._on_row_clicked)
        row.action_requested.connect(self._on_row_action)
        return row

    def _empty_row(self, icon_name: str, title: str, hint: str):
        return MenuRow(
            self.theme,
            title,
            subtitle=hint,
            icon=icons.icon(icon_name, self.theme.subtext, 20),
            dim=True,
        )

    def _on_row_clicked(self, row, new_tab: bool) -> None:
        meta = getattr(row, "_meta", None) or {}
        url = meta.get("url")
        if not url:
            return
        panel = self._dropdowns.get(meta.get("kind"))
        if panel is not None:
            panel.hide()
        if new_tab:
            self.new_tab(QUrl(url))
        else:
            self._open_in_current_tab(url)

    def _retry_download(self, url) -> None:
        """用下载 URL 重新发起下载（经共享 profile；新 rec + 新 DB 行，旧行保留）。"""
        if not url:
            return
        tab = self._current()
        page = tab.view.page() if isinstance(tab, Tab) else None
        if page is None:
            return
        page.download(QUrl(url))

    def _on_row_action(self, row, action_id: str) -> None:
        """行右侧按钮：删除/移除、下载控制（暂停/继续/取消/打开/目录）。"""
        meta = getattr(row, "_meta", None) or {}
        kind = meta.get("kind")
        if action_id in ("delete", "remove"):
            if kind == "history":
                history.remove_by_id(self.conn, meta.get("key"))
            elif kind == "bookmark":
                bookmarks.remove(self.conn, meta.get("key"))
                self._refresh_bookmark_icon()
            elif kind == "download":
                rec = meta.get("rec")
                if rec is not None:
                    self.downloads.remove(rec)
                elif meta.get("key") is not None:
                    downloads_store.remove(self.conn, meta.get("key"))
            self._refresh_dropdown(kind)
            return
        path = meta.get("path") or ""
        if action_id == "refresh":
            self._retry_download(meta.get("retry_url"))
            self._refresh_dropdown(kind)
            return
        if action_id == "open":
            self.downloads.open_file(path)
            return
        if action_id == "folder":
            self.downloads.reveal_in_explorer(path)
            return
        rec = meta.get("rec")
        if rec is None:
            return
        if action_id == "pause":
            self.downloads.pause(rec)
        elif action_id == "resume":
            self.downloads.resume(rec)
        elif action_id == "cancel":
            self.downloads.cancel(rec)
        else:
            return
        self._refresh_dropdown("download")

    def _refresh_dropdown(self, kind: str) -> None:
        panel = getattr(self, "_dropdowns", {}).get(kind)
        if panel is None or not panel.isVisible():
            return
        if kind == "history":
            self._fill_history_panel(panel)
        elif kind == "bookmarks":
            self._fill_bookmarks_panel(panel)
        elif kind == "download":
            self._fill_download_panel(panel)

    @staticmethod
    def _human_size(n) -> str:
        n = float(n or 0)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if n < 1024 or unit == "TB":
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"

    def _human_speed(self, n) -> str:
        return f"{self._human_size(n)}/s"

    def _download_status(self, rec: dict) -> str:
        if rec["canceled"]:
            return "已取消 / 失败"
        total = rec["total"] or 0
        received = rec["received"] or 0
        if rec["finished"]:
            return f"已完成 · {self._human_size(total)}"
        if rec.get("is_paused"):
            if total > 0:
                return f"已暂停 · {self._human_size(received)} / {self._human_size(total)}"
            return f"已暂停 · {self._human_size(received)}"
        speed = rec.get("speed", 0.0) or 0.0
        parts = []
        if total > 0:
            parts.append(f"{int(received * 100 / total)}%")
        if speed > 0:
            parts.append(self._human_speed(speed))
        if total > 0:
            parts.append(f"{self._human_size(received)} / {self._human_size(total)}")
        else:
            parts.append(self._human_size(received))
        return " · ".join(parts)

    def _context_popup(self) -> ContextMenu:
        """右键菜单复用一个常驻自绘弹出层。

        非 QMenu：QMenu 永远是 translucent/layered 窗口且悬停重绘昂贵；浮在
        播放中的视频上会拖累 GUI 线程 + DWM 合成。见 ui/context_menu.py。
        """
        popup = getattr(self, "_ctx_popup", None)
        if popup is None:
            popup = ContextMenu(self.theme)
            self._ctx_popup = popup
        return popup

    def _show_context_menu(self, tab, req, pos) -> None:
        """自定义中文右键菜单（按 lastContextMenuRequest 上下文动态构建）。"""
        page = tab.view.page()
        if page is None:
            return
        entries: list = []

        def page_action(text, wa):
            act = page.action(wa)
            enabled = bool(act.isEnabled()) if act is not None else False
            entries.append(
                menu_action(text, lambda w=wa: page.triggerAction(w), enabled)
            )

        link = req.linkUrl() if req is not None else None
        media = req.mediaUrl() if req is not None else None
        if req is not None:
            mtype = req.mediaType()
            selected = req.selectedText() or ""
            editable = bool(req.isContentEditable())
            flags = req.editFlags()
        else:
            mtype = QWebEngineContextMenuRequest.MediaType.MediaTypeNone
            selected = ""
            editable = False
            flags = QWebEngineContextMenuRequest.EditFlag(0)

        has_link = link is not None and link.isValid()
        has_image = (
            media is not None and media.isValid()
            and mtype == QWebEngineContextMenuRequest.MediaType.MediaTypeImage
        )

        if has_link:
            entries.append(menu_action("在新标签打开链接", lambda u=link: self.new_tab(u)))
            entries.append(menu_action("链接另存为", lambda u=link: page.download(u)))
            entries.append(
                menu_action(
                    "复制链接地址",
                    lambda u=link: QApplication.clipboard().setText(u.toString()),
                )
            )
            entries.append(menu_separator())
        if has_image:
            entries.append(menu_action("图片另存为", lambda u=media: page.download(u)))
            entries.append(
                menu_action(
                    "复制图片地址",
                    lambda u=media: QApplication.clipboard().setText(u.toString()),
                )
            )
            entries.append(menu_action("在新标签打开图片", lambda u=media: self.new_tab(u)))
            entries.append(menu_separator())
        if editable:
            Edit = QWebEngineContextMenuRequest.EditFlag
            for text, flag, wa in (
                ("撤销", Edit.CanUndo, QWebEnginePage.WebAction.Undo),
                ("重做", Edit.CanRedo, QWebEnginePage.WebAction.Redo),
                ("剪切", Edit.CanCut, QWebEnginePage.WebAction.Cut),
                ("复制", Edit.CanCopy, QWebEnginePage.WebAction.Copy),
                ("粘贴", Edit.CanPaste, QWebEnginePage.WebAction.Paste),
                ("全选", Edit.CanSelectAll, QWebEnginePage.WebAction.SelectAll),
            ):
                if flags & flag:
                    page_action(text, wa)
            entries.append(menu_separator())
        elif selected:
            entries.append(
                menu_action(
                    "复制",
                    lambda: page.triggerAction(QWebEnginePage.WebAction.Copy),
                )
            )
            engine = self.settings.get("search_engine", "bing")
            template = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["bing"])
            engine_label = {
                "bing": "Bing", "baidu": "百度",
                "duckduckgo": "DuckDuckGo", "google": "Google",
            }.get(engine, engine)
            label = selected if len(selected) <= 20 else selected[:20] + "\u2026"
            url = template.format(q=quote_plus(selected))
            entries.append(
                menu_action(
                    f"用 {engine_label} 搜索\u201c{label}\u201d",
                    lambda u=url: self.new_tab(QUrl(u)),
                )
            )
            entries.append(menu_separator())

        page_action("后退", QWebEnginePage.WebAction.Back)
        page_action("前进", QWebEnginePage.WebAction.Forward)
        page_action("刷新", QWebEnginePage.WebAction.Reload)

        popup = self._context_popup()
        popup.set_entries(entries)
        popup.popup(pos)

    def _fill_history_panel(self, panel: DropdownPanel) -> None:
        panel.set_header(
            "历史记录", "查看全部",
            lambda: self.new_tab(QUrl("purebrowser://history")),
        )
        rows = history.recent(self.conn, limit=150)
        if not rows:
            panel.set_sections(
                [(None, [self._empty_row("clock", "暂无历史记录",
                                         "浏览过的网页会出现在这里")])]
            )
            return
        today = date.today()
        groups = {"今天": [], "昨天": [], "更早": []}
        for r in rows:
            visited = date.fromtimestamp(r["visited_at"])
            if visited == today:
                groups["今天"].append(r)
            elif visited == today - timedelta(days=1):
                groups["昨天"].append(r)
            else:
                groups["更早"].append(r)
        sections = []
        for label in ("今天", "昨天", "更早"):
            items = groups[label][:40]
            if not items:
                continue
            widgets = []
            for r in items:
                url = r["url"]
                host = r["host"] or (urlparse(url).hostname or "")
                widgets.append(self._make_row(
                    title=r["title"] or url,
                    subtitle=host or url,
                    icon=self._host_icon(host),
                    url=url, kind="history", key=r["id"],
                ))
            sections.append((label, widgets))
        panel.set_sections(sections)

    def _fill_bookmarks_panel(self, panel: DropdownPanel) -> None:
        panel.set_header("书签", "清空", self._clear_bookmarks)
        rows = bookmarks.list_all(self.conn)
        if not rows:
            panel.set_sections(
                [(None, [self._empty_row("bookmark", "暂无书签",
                                         "点击地址栏星标即可收藏")])]
            )
            return
        widgets = []
        for r in rows:
            url = r["url"]
            host = urlparse(url).hostname or ""
            widgets.append(self._make_row(
                title=r["title"] or url,
                subtitle=host or url,
                icon=self._host_icon(host),
                url=url, kind="bookmark", key=url,
            ))
        panel.set_sections([(None, widgets)])

    def _fill_download_panel(self, panel: DropdownPanel) -> None:
        panel.set_header("下载", "打开文件夹", self.downloads.open_folder)

        live = list(self.downloads.records)
        live_ids = {r.get("db_id") for r in live if r.get("db_id") is not None}
        hist = [row for row in downloads_store.list_recent(self.conn, 200)
                if row["id"] not in live_ids]

        entries = [(r.get("created_at", 0), r, None) for r in live]
        entries += [(h["created_at"], None, h) for h in hist]
        entries.sort(key=lambda e: e[0], reverse=True)

        if not entries:
            panel.set_sections(
                [(None, [self._empty_row("download", "暂无下载",
                                         "下载的文件会显示在这里")])]
            )
            panel._download_rows = {}
            panel._active_ids = set()
            return

        groups = {"进行中": [], "已完成": [], "失败": []}
        for _created, rec, h in entries:
            if rec is not None:
                if not rec["finished"]:
                    groups["进行中"].append((rec, h))
                elif rec["canceled"]:
                    groups["失败"].append((rec, h))
                else:
                    groups["已完成"].append((rec, h))
            else:
                if h["state"] == "completed":
                    groups["已完成"].append((rec, h))
                elif h["state"] in ("cancelled", "interrupted"):
                    groups["失败"].append((rec, h))
                else:
                    groups["进行中"].append((rec, h))

        sections = []
        dl_rows: dict = {}
        active_ids: set = set()
        for label, items, icon_name in (
            ("进行中", groups["进行中"], "download"),
            ("已完成", groups["已完成"], "file"),
            ("失败", groups["失败"], "alert"),
        ):
            if not items:
                continue
            widgets = []
            for rec, h in items:
                if rec is not None:
                    row = self._make_row(
                        title=rec["filename"],
                        subtitle=self._download_status(rec),
                        icon=icons.icon(icon_name, self.theme.subtext, 20),
                        kind="download", key=rec.get("db_id"),
                        buttons=self._download_buttons(rec),
                        path=rec["path"], rec=rec, retry_url=rec.get("url"),
                        progress=self._percent(rec) if not rec["finished"] else None,
                    )
                    if not rec["finished"]:
                        dl_rows[rec.get("db_id")] = row
                        active_ids.add(rec.get("db_id"))
                else:
                    row = self._make_row(
                        title=h["filename"] or h["path"],
                        subtitle=self._history_status(h),
                        icon=icons.icon(icon_name, self.theme.subtext, 20),
                        kind="download", key=h["id"],
                        buttons=self._history_buttons(h),
                        path=h["path"], rec=None, retry_url=h["url"],
                    )
                widgets.append(row)
            sections.append((label, widgets))
        panel.set_sections(sections)
        panel._download_rows = dl_rows
        panel._active_ids = active_ids

    def _update_download_panel(self) -> None:
        """下载面板可见时每 200ms 原地刷新进度/速度/体积。"""
        panel = self._dropdowns.get("download")
        if panel is None or not panel.isVisible():
            self._dl_live_timer.stop()
            return
        active = [r for r in self.downloads.records if not r["finished"]]
        current_ids = {r.get("db_id") for r in active}
        if current_ids != getattr(panel, "_active_ids", set()):
            self._fill_download_panel(panel)
            return
        rows = getattr(panel, "_download_rows", {})
        for rec in active:
            row = rows.get(rec.get("db_id"))
            if row is not None:
                row.set_progress(self._percent(rec))
                row.set_subtitle(self._download_status(rec))

    def _download_buttons(self, rec: dict) -> list:
        color = self.theme.subtext
        if rec["canceled"]:
            buttons = []
            if rec.get("url"):
                buttons.append({"id": "refresh", "icon": icons.icon("refresh", color, 16),
                                "tooltip": "重试下载"})
            buttons.append({"id": "folder", "icon": icons.icon("folder", color, 16),
                            "tooltip": "打开所在目录"})
            buttons.append({"id": "remove", "icon": icons.icon("cancel", color, 16),
                            "tooltip": "从列表移除"})
            return buttons
        if rec["finished"]:
            return [
                {"id": "open", "icon": icons.icon("open", color, 16), "tooltip": "打开文件"},
                {"id": "folder", "icon": icons.icon("folder", color, 16), "tooltip": "打开所在目录"},
                {"id": "remove", "icon": icons.icon("cancel", color, 16), "tooltip": "从列表移除"},
            ]
        pause = (
            {"id": "resume", "icon": icons.icon("play", color, 16), "tooltip": "继续"}
            if rec.get("is_paused")
            else {"id": "pause", "icon": icons.icon("pause", color, 16), "tooltip": "暂停"}
        )
        return [
            pause,
            {"id": "cancel", "icon": icons.icon("cancel", color, 16), "tooltip": "取消下载"},
        ]

    def _history_status(self, row) -> str:
        state = row["state"]
        reason = row["interrupt_reason"] or ""
        size = self._human_size(row["total"])
        if state == "completed":
            return f"已完成 · {size}"
        if state == "cancelled":
            return "已取消" + (f" · {reason}" if reason else "")
        if state == "interrupted":
            return "已中断" + (f" · {reason}" if reason else "")
        return f"进行中 · {size}"

    def _history_buttons(self, row) -> list:
        color = self.theme.subtext
        exists = bool(row["path"]) and Path(row["path"]).exists()
        buttons = []
        if row["state"] in ("cancelled", "interrupted") and row["url"]:
            buttons.append({"id": "refresh", "icon": icons.icon("refresh", color, 16),
                            "tooltip": "重试下载"})
        if row["state"] == "completed" and exists:
            buttons.append({"id": "open", "icon": icons.icon("open", color, 16), "tooltip": "打开文件"})
        if exists:
            buttons.append({"id": "folder", "icon": icons.icon("folder", color, 16), "tooltip": "打开所在目录"})
        buttons.append({"id": "remove", "icon": icons.icon("cancel", color, 16), "tooltip": "从列表移除"})
        return buttons

    @staticmethod
    def _percent(rec: dict) -> int:
        total = rec.get("total") or 0
        received = rec.get("received") or 0
        if total > 0:
            return int(received * 100 / total)
        return 0

    def _refresh_download_button(self) -> None:
        n = self.downloads.active_count()
        self.download_btn.setIcon(icons.icon("download", self.theme.text))
        if n > 0:
            self.dl_badge.setText(str(n) if n < 100 else "99+")
            self.dl_badge.setVisible(True)
            self._position_download_badge()
        else:
            self.dl_badge.setVisible(False)

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
        self._tab_urls[tab] = "" if page is not None else url.toString()
        self._install_tab_close(tab)
        self.tabs.setCurrentIndex(idx)
        tab.title_changed.connect(lambda t: self._set_tab_title(tab, t))
        tab.url_changed.connect(lambda u: self._on_url_changed(tab, u))
        tab.load_started.connect(self._on_load_started)
        tab.load_finished.connect(self._on_load_finished)
        tab.page_loaded.connect(self._on_page_loaded)
        tab.new_page_requested.connect(self._on_new_page_requested)
        tab.fullscreen_toggled.connect(self._on_fullscreen_toggled)
        tab.view.page().findTextFinished.connect(self._on_find_result)
        tab.view.page().shortcut_unhandled.connect(
            lambda action, t=tab: self._on_shortcut_unhandled(t, action)
        )
        tab.load_finished.connect(
            lambda _ok=False, t=tab: self._apply_site_zoom(t.view, t.view.url())
        )
        tab.icon_changed.connect(lambda icon, t=tab: self._on_tab_icon(t, icon))
        tab.view.context_menu_requested.connect(
            lambda req, pos, t=tab: self._show_context_menu(t, req, pos)
        )
        self._apply_tab_icon(tab)
        tab.view.installEventFilter(self)
        self._ensure_wheel_filter(tab.view)
        QTimer.singleShot(0, lambda v=tab.view: self._ensure_wheel_filter(v))
        if page is None:
            tab.load(url)
        self._relayout_tabs()
        self._schedule_session_save()
        return tab

    def _on_new_page_requested(self, page: QWebEnginePage) -> None:
        self.new_tab(QUrl("about:blank"), page=page)

    def _close_tab(self, idx: int) -> None:
        if idx < 0:
            return
        if self.tabs.count() <= 1:
            return
        w = self.tabs.widget(idx)
        if isinstance(w, Tab):
            # 用缓存 URL/标题（关闭时读 view 会与在途加载竞态 → AV）。
            url = self._tab_urls.get(w, "")
            if url:
                self._closed_tabs.append((url, self._tab_full_titles.get(w, "")))
                if len(self._closed_tabs) > 20:
                    self._closed_tabs.pop(0)
        self.tabs.removeTab(idx)
        self._tab_full_titles.pop(w, None)
        self._tab_urls.pop(w, None)
        if isinstance(w, Tab):
            self._wheel_targets.discard(w.view.focusProxy())
        w.deleteLater()
        self._relayout_tabs()
        self._schedule_session_save()

    def _current(self) -> Tab:
        return self.tabs.currentWidget()  # type: ignore[return-value]

    # ---------- session / recently closed ----------
    def _schedule_session_save(self) -> None:
        if getattr(self, "_session_timer", None) is not None:
            self._session_timer.start()

    def _save_session(self) -> None:
        # 恢复提示未决时不写盘，避免把上次会话覆盖成占位 newtab。
        if getattr(self, "_pending_restore", None) is not None:
            return
        try:
            tabs = []
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, Tab):
                    tabs.append({"url": self._tab_urls.get(w, ""),
                                 "title": self._tab_full_titles.get(w, "")})
            ng = self._last_normal_rect or self.normalGeometry()
            window = {
                "maximized": bool(self._is_zoomed()),
                "x": ng.x(), "y": ng.y(), "w": ng.width(), "h": ng.height(),
            }
            session.save(self.data_dir, {
                "tabs": tabs, "active": self.tabs.currentIndex(), "window": window,
            })
        except Exception:
            pass

    def _reopen_closed_tab(self) -> None:
        while self._closed_tabs:
            url, _title = self._closed_tabs.pop()
            if url:
                self.new_tab(QUrl(url))
                return

    # ---------- favicons ----------
    def _globe_icon(self) -> QIcon:
        return icons.icon("globe", self.theme.subtext, 16)

    def _apply_tab_icon(self, tab: Tab) -> None:
        """按当前 host 的缓存图标回填标签；无缓存/空 host 用 globe 兜底。"""
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        host = urlparse(tab.view.url().toString()).hostname or ""
        pixmap = favicons.get(self.conn, host) if host else None
        icon = QIcon(pixmap) if pixmap is not None else self._globe_icon()
        self.tabs.tabBar().setTabIcon(idx, icon)

    def _on_tab_icon(self, tab: Tab, icon: QIcon) -> None:
        """view.iconChanged → 归一化 PNG 落库 → 回填标签图标。"""
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        host = urlparse(tab.view.url().toString()).hostname or ""
        if not host or icon is None or icon.isNull():
            return
        png = favicons.icon_to_png(icon)
        if png is None:
            return
        favicons.save(self.conn, host, png)
        pixmap = favicons.get(self.conn, host)
        if pixmap is not None:
            self.tabs.tabBar().setTabIcon(idx, QIcon(pixmap))

    def _set_tab_title(self, tab: Tab, title: str) -> None:
        # 已关闭（deleteLater 期间迟到）的标签不再写缓存，避免字典持有僵尸 key。
        if self.tabs.indexOf(tab) < 0:
            return
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
        # 已关闭的标签迟到信号直接忽略（避免僵尸 key 及访问垂死的 view）。
        if self.tabs.indexOf(tab) < 0:
            return
        # 缩放按 page 且跨导航保持，URL 一变就按站点应用（查不到则复位 1.0），
        # 避免上个站点的缩放泄漏到新站点。
        self._apply_site_zoom(tab.view, url)
        self._ensure_wheel_filter(tab.view)
        self._apply_tab_icon(tab)
        self._tab_urls[tab] = url.toString()
        self._schedule_session_save()
        if tab is self.tabs.currentWidget():
            self.url_bar.setText(display_url(url))
            self.url_bar.setCursorPosition(0)

    def _sync_from_tab(self, _idx: int) -> None:
        # 切换标签后旧高亮已无意义，自动收起查找浮层。
        if getattr(self, "find_hud", None) is not None and self.find_hud.isVisible():
            self._hide_find_bar()
        tab = self.tabs.currentWidget()
        if isinstance(tab, Tab):
            self._ensure_wheel_filter(tab.view)
            self.url_bar.setText(display_url(tab.current_url()))
            self._refresh_bookmark_icon()
            self._schedule_session_save()

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
        # 兜底：退出前再保存一次会话（debounce 可能还没触发）。
        self._save_session()
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, Tab):
                w.view.setPage(None)
        self.blocker.close()
        self.conn.close()
        super().closeEvent(event)
