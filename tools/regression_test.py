"""PureBrowser 回归测试（不联网）。

覆盖容易复发的修复::

    1  右键上下文菜单不再泄漏：反复弹开 + 关闭后，MainWindow 下的 QMenu
       数量必须回到基线（历史/书签/下载三个常驻菜单）。回归原因：QMenu
       设了 WA_DeleteOnClose，但用户点别处关闭走 hide()，不会删除，累积的
       带阴影弹出菜单会拖慢合成器（视频卡顿）。

    2  Ctrl+F 桥接：PurePage.javaScriptConsoleMessage 收到注入脚本的暗号
       （__PB_FIND__）时发出 shortcut_unhandled 信号；其它 console 消息不发。

    3  最大化状态下全屏，客户区必须盖满窗口（不能按工作区裁而露出任务栏）。
       回归原因：_adjust_maximized_client 在 IsZoomed 时一律对齐 rcWork，
       而全屏窗口仍带 WS_MAXIMIZE。

    4  右键菜单复用"自绘不透明弹出层"：不得退化成 layered（否则 DWM 逐帧
       alpha 合成）；工具栏不得再挂 QGraphicsDropShadowEffect（每次重绘 +3ms）。

    5  下载下拉面板：进行中任务要有进度条 + 速度/体积；角标随任务显隐；
       内容过长时可滚动。

    6  会话：窗口尺寸/位置落盘、未决恢复提示时不覆盖会话、_load_tabs 生效。

用法::

    .venv\\Scripts\\python.exe tools\\regression_test.py

退出码:
    0 = 全部通过
    1 = 失败
"""
from __future__ import annotations

import sys
import tempfile
import time
import traceback
from pathlib import Path

# 注册 purebrowser:// scheme 必须在 QApplication 之前完成（与 app.py 一致）。
from PyQt6.QtWebEngineCore import QWebEngineUrlScheme

_scheme = QWebEngineUrlScheme(b"purebrowser")
_scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
_scheme.setFlags(
    QWebEngineUrlScheme.Flag.SecureScheme
    | QWebEngineUrlScheme.Flag.LocalAccessAllowed
)
QWebEngineUrlScheme.registerScheme(_scheme)

import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, Qt, QTimer, QUrl
from PyQt6.QtGui import QHideEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from purebrowser.ui.tab import FIND_SENTINEL, PurePage
from purebrowser.ui.window import MainWindow
from purebrowser.data import session

CYCLES = 25

_user32 = ctypes.WinDLL("user32")
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]

_fails: list[str] = []
_checks = 0


def emit(line: str) -> None:
    print(line, flush=True)


def check(name: str, ok: bool, detail: str = "") -> None:
    global _checks
    _checks += 1
    if ok:
        emit(f"[OK]   {name}")
    else:
        msg = f"{name}: {detail}" if detail else name
        emit(f"[FAIL] {msg}")
        _fails.append(msg)


def drain(app: QApplication) -> None:
    """强制处理 deleteLater 的延迟删除。"""
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_shortcut_bridge() -> None:
    page = PurePage(QWebEngineProfile.defaultProfile())
    got: list[str] = []
    page.shortcut_unhandled.connect(got.append)

    level = QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel
    page.javaScriptConsoleMessage(level, FIND_SENTINEL, 0, "hook")
    check("Ctrl+F 暗号触发信号", got == ["find"], f"got={got!r}")

    page.javaScriptConsoleMessage(level, "ordinary log", 0, "page")
    check("普通 console 不触发信号", got == ["find"], f"got={got!r}")


def _hide_ctx(win: MainWindow) -> None:
    popup = getattr(win, "_ctx_popup", None)
    if popup is not None:
        popup.hide()


def _is_layered(widget) -> bool:
    ex = int(_user32.GetWindowLongPtrW(wintypes.HWND(int(widget.winId())), -20))
    return bool(ex & 0x00080000)


def test_menu_no_leak(app: QApplication, win: MainWindow) -> None:
    tab = win._current()

    # 预热：首次右键会创建常驻弹出层，把它计入基线。
    win._show_context_menu(tab, None, QPoint(20, 20))
    drain(app)
    _hide_ctx(win)
    drain(app)

    popup0 = getattr(win, "_ctx_popup", None)
    baseline = len(win.findChildren(QMenu))
    growth = 0

    for _ in range(CYCLES):
        win._show_context_menu(tab, None, QPoint(20, 20))
        app.processEvents()
        _hide_ctx(win)
        drain(app)
        current = len(win.findChildren(QMenu))
        if current != baseline:
            growth += current - baseline

    check(
        f"右键菜单不泄漏（{CYCLES} 次）",
        growth == 0 and popup0 is not None and getattr(win, "_ctx_popup", None) is popup0,
        f"基线={baseline} 增长={growth} 复用={getattr(win, '_ctx_popup', None) is popup0}",
    )

    # 自绘弹出层必须是非 layered（否则仍会被 DWM 逐帧 alpha 合成）。
    win._show_context_menu(tab, None, QPoint(20, 20))
    app.processEvents()
    popup = win._ctx_popup
    check("右键菜单为非分层窗口（非 layered）", not _is_layered(popup), _is_layered(popup))
    _hide_ctx(win)
    drain(app)

    # 工具栏不得再挂 QGraphicsDropShadowEffect（每次重绘 +3ms）。
    check(
        "工具栏无 QGraphicsDropShadowEffect",
        win.toolbar.graphicsEffect() is None,
        f"effect={win.toolbar.graphicsEffect()!r}",
    )


def test_download_panel(app: QApplication, win: MainWindow) -> None:
    """下载面板：进行中任务要显示进度条 + 速度/体积；角标随任务显隐；面板可滚动。"""
    from purebrowser.ui.menu_rows import MenuRow

    rec = {
        "req": None, "filename": "regression.bin", "path": "C:/x/regression.bin",
        "total": 100_000_000, "received": 45_000_000, "state": None,
        "interrupt_reason": "", "is_paused": False, "finished": False,
        "canceled": False, "url": "https://example.com/a.bin",
        "mime": "application/octet-stream", "created_at": int(time.time()),
        "finished_at": None, "state_text": "inprogress", "db_id": 999999,
        "speed": 1_500_000.0,
    }
    win.downloads.records.append(rec)
    try:
        win._refresh_download_button()
        check(
            "下载中显示红色角标",
            win.dl_badge.isVisible() and win.dl_badge.text() == "1",
            f"vis={win.dl_badge.isVisible()} text={win.dl_badge.text()}",
        )
        win._toggle_dropdown("download", win.download_btn)
        app.processEvents()
        panel = win._dropdowns["download"]
        row = next((r for r in panel.rows() if getattr(r, "_bar", None) is not None), None)
        if row is None:
            check("下载面板显示进度条+速度+体积", False, "无进度条行")
        else:
            sub = row._sub.text()
            check(
                "下载面板显示进度条+速度+体积",
                row._bar.value() == 45 and "45%" in sub and "MB" in sub,
                f"progress={row._bar.value()} sub={sub!r}",
            )
        panel.hide()
    finally:
        win.downloads.records.remove(rec)
    win._refresh_download_button()
    check("无下载时隐藏角标", not win.dl_badge.isVisible(), f"vis={win.dl_badge.isVisible()}")

    panel = win._dropdowns["history"]
    rows = [MenuRow(win.theme, f"item {i}", subtitle="example.com") for i in range(60)]
    panel.set_sections([("今天", rows)])
    panel.open_below(win.history_btn)
    app.processEvents()
    sb = panel._scroll.verticalScrollBar()
    check("下拉面板内容过长时可滚动", sb.maximum() > 0, f"scroll_max={sb.maximum()}")
    panel.hide()


def test_session(win: MainWindow) -> None:
    """会话：pending 决策、窗口状态落盘、未决时不覆盖、_load_tabs。"""
    p = win._compute_pending_restore({
        "tabs": [{"url": "https://x"}, {"url": "purebrowser://newtab"},
                 {"url": "https://y"}],
        "active": 2,
    })
    check(
        "会话恢复：过滤 newtab 且定位 active",
        p is not None and [t["url"] for t in p[0]] == ["https://x", "https://y"] and p[1] == 1,
        f"pending={p}",
    )
    check("无标签时不提示恢复", win._compute_pending_restore({"tabs": []}) is None)

    win.resize(1010, 720)
    win.move(140, 160)
    QTest.qWait(300)
    win._save_session()
    w = session.load(win.data_dir).get("window") or {}
    g = win.geometry()
    check(
        "窗口尺寸/位置写入会话",
        abs(w.get("w", 0) - g.width()) <= 1 and abs(w.get("h", 0) - g.height()) <= 1
        and abs(w.get("x", 0) - g.x()) <= 1 and abs(w.get("y", 0) - g.y()) <= 1,
        f"window={w} geom={g}",
    )

    # 恢复提示未决时不得写盘（否则会把上次会话覆盖成占位 newtab）
    before = session.session_path(win.data_dir).read_text(encoding="utf-8")
    win._pending_restore = ([{"url": "about:blank"}], 0)
    win.new_tab(QUrl("about:blank"))
    win._save_session()
    after = session.session_path(win.data_dir).read_text(encoding="utf-8")
    check("恢复提示未决时不覆盖会话", before == after, "session.json changed")
    win._pending_restore = None

    n0 = win.tabs.count()
    win._load_tabs([{"url": "about:blank"}, {"url": "about:blank"}], 1)
    check(
        "_load_tabs 载入标签页",
        win.tabs.count() >= n0 and win.tabs.currentIndex() >= 0,
        f"count={win.tabs.count()} active={win.tabs.currentIndex()}",
    )


def test_startup_max_icon(win: MainWindow) -> None:
    """回归：启动即最大化时，标题栏 max 键必须显示"还原"。

    历史 bug：_on_window_state_changed 直接用信号 state 判定；该自绘无边框窗口
    会收到"只带 WindowActive、不带 Maximized"的过时事件，把已最大化窗口的图标
    刷回"最大化"。现在改为延后用 isMaximized() 对账。这里显式派发过时事件验证。
    """
    win._start_maximized = True
    win._start_rect = None
    win.showNormal()
    QTest.qWait(150)
    win.start()
    QTest.qWait(400)
    check(
        "启动最大化时 max 键显示还原",
        win.isMaximized() and win.win_max._tip == "还原",
        f"isMax={win.isMaximized()} tip={win.win_max._tip!r}",
    )
    wh = win.windowHandle()
    if wh is not None:
        wh.windowStateChanged.emit(Qt.WindowState.WindowActive)  # 过时事件
        QTest.qWait(150)
        check(
            "过时的激活事件不刷错已最大化窗口的图标",
            win.isMaximized() and win.win_max._tip == "还原",
            f"isMax={win.isMaximized()} tip={win.win_max._tip!r}",
        )
    win.win_max.click()
    QTest.qWait(300)
    check(
        "点击 max 键切回窗口化（状态机）",
        (not win._maximized) and (not win._is_zoomed())
        and win.win_max._tip == "最大化",
        f"_max={win._maximized} zoom={win._is_zoomed()} tip={win.win_max._tip!r}",
    )
    win.win_max.click()
    QTest.qWait(300)
    check(
        "再次点击切回最大化",
        win._maximized and win._is_zoomed() and win.win_max._tip == "还原",
        f"_max={win._maximized} zoom={win._is_zoomed()} tip={win.win_max._tip!r}",
    )
    win.showNormal()
    QTest.qWait(300)
    check(
        "还原窗口后 max 键显示最大化",
        (not win.isMaximized()) and win.win_max._tip == "最大化",
        f"isMax={win.isMaximized()} tip={win.win_max._tip!r}",
    )


def test_row_hover_clears(win: MainWindow) -> None:
    """回归：下拉富行的高亮必须能可靠清除（子控件 Leave、行隐藏）。"""
    from purebrowser.ui.menu_rows import MenuRow

    row = MenuRow(win.theme, "测试行", subtitle="example.com")
    row._set_hovered(True)
    # 给子控件发 Leave：事件过滤器按光标位置对账（测试环境光标不在该行上）→ 清除
    children = row.findChildren(QWidget)
    for child in children:
        QApplication.sendEvent(child, QEvent(QEvent.Type.Leave))
    check("子控件 Leave 会清除整行高亮", row._hovered is False, f"hovered={row._hovered}")

    row._set_hovered(True)
    row.hideEvent(QHideEvent())
    check("行隐藏时清除高亮", row._hovered is False, f"hovered={row._hovered}")
    row.deleteLater()


def test_restore_size_and_heal(win: MainWindow) -> None:
    """窗口状态：坏矩形自愈、最大化不污染窗口化尺寸、还原几何正确。"""
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QGuiApplication

    wa = QGuiApplication.primaryScreen().availableGeometry()

    # 自愈：maximized 且尺寸≈工作区（旧版写坏的值）→ 丢弃，改用默认窗口矩形
    win._apply_startup_geometry({
        "maximized": True, "x": wa.left(), "y": wa.top(),
        "w": wa.width(), "h": wa.height(),
    })
    check(
        "坏的工作区矩形被自愈丢弃",
        win._start_rect != QRect(wa.left(), wa.top(), wa.width(), wa.height())
        and win._start_rect.width() <= 1200,
        f"start_rect={win._start_rect}",
    )

    # 有效的窗口化矩形应原样采纳
    win._apply_startup_geometry({"maximized": True, "x": 150, "y": 120,
                                 "w": 880, "h": 620})
    check(
        "有效窗口化矩形被采纳",
        win._start_rect == QRect(150, 120, 880, 620),
        f"start_rect={win._start_rect}",
    )

    # 最大化不得把窗口化尺寸写成最大化几何
    win.showNormal()
    QTest.qWait(200)
    win.resize(1000, 700)
    win.move(180, 140)
    QTest.qWait(250)
    before = win._last_normal_rect
    win._toggle_maximize()
    QTest.qWait(350)
    check(
        "最大化不污染窗口化尺寸",
        win._last_normal_rect == before,
        f"before={before} after={win._last_normal_rect}",
    )
    win._toggle_maximize()
    QTest.qWait(350)

    # 最大化启动 → 点还原，几何 == 保存的窗口化矩形
    win._start_maximized = True
    win._start_rect = QRect(160, 130, 900, 640)
    win.showNormal()
    QTest.qWait(150)
    win.start()
    QTest.qWait(400)
    win.win_max.click()
    QTest.qWait(400)
    g = win.geometry()
    check(
        "还原后几何 == 保存的窗口化矩形",
        abs(g.width() - 900) <= 20 and abs(g.height() - 640) <= 20,
        f"geom={g}",
    )
    win.showNormal()
    QTest.qWait(200)


def _win_rects(win: MainWindow):
    h = wintypes.HWND(int(win.winId()))
    wr = wintypes.RECT()
    _user32.GetWindowRect(h, ctypes.byref(wr))
    cr = wintypes.RECT()
    _user32.GetClientRect(h, ctypes.byref(cr))
    pt = wintypes.POINT(0, 0)
    _user32.ClientToScreen(h, ctypes.byref(pt))
    window = (wr.left, wr.top, wr.right - wr.left, wr.bottom - wr.top)
    client = (pt.x, pt.y, cr.right - cr.left, cr.bottom - cr.top)
    return window, client


def test_fullscreen_client_gap(win: MainWindow) -> None:
    """回归：最大化状态下全屏，客户区不得被裁到工作区而露出任务栏。

    根因曾是 _adjust_maximized_client 在 IsZoomed 时一律对齐 rcWork，
    而全屏窗口仍带 WS_MAXIMIZE，导致客户端底部缺任务栏高度（浅蓝色边角）。
    """
    win.showMaximized()
    QTest.qWait(400)
    start_window, _ = _win_rects(win)

    for n in (1, 2):
        win.enter_fullscreen(source="video")
        QTest.qWait(300)
        window, client = _win_rects(win)
        gap = (window[1] + window[3]) - (client[1] + client[3])
        check(
            f"全屏#{n} 客户区盖满窗口（无任务栏缺口）",
            gap == 0,
            f"window={window} client={client} gap={gap}",
        )
        win.exit_fullscreen()
        QTest.qWait(300)

    final_window, _ = _win_rects(win)
    close = all(abs(a - b) <= 2 for a, b in zip(final_window, start_window))
    check(
        "退出全屏回到最大化几何",
        close,
        f"start={start_window} final={final_window}",
    )
    win.showNormal()
    QTest.qWait(200)


def main() -> int:
    if sys.platform != "win32":
        emit("[SKIP] 该测试依赖 Windows 原生窗口 / QWebEngine")
        return 0

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    data_dir = Path(tempfile.mkdtemp(prefix="pb_regression_"))
    win = MainWindow(data_dir)
    win.resize(900, 640)
    win.show()
    app.processEvents()

    results = {"code": 1}

    def run() -> None:
        try:
            test_shortcut_bridge()
            test_menu_no_leak(app, win)
            test_download_panel(app, win)
            test_session(win)
            test_startup_max_icon(win)
            test_restore_size_and_heal(win)
            test_row_hover_clears(win)
            test_fullscreen_client_gap(win)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
            check("未捕获异常", False, "见上方 traceback")
        results["code"] = 1 if _fails else 0
        QTimer.singleShot(0, close_win)

    def close_win() -> None:
        try:
            win.close()
        except Exception:  # noqa: BLE001
            pass
        QTimer.singleShot(250, lambda: app.exit(results["code"]))

    emit("=" * 60)
    emit("PureBrowser regression test")
    emit("=" * 60)
    QTimer.singleShot(300, run)
    QTimer.singleShot(120000, lambda: app.exit(1))

    code = app.exec()
    emit("=" * 60)
    emit(f"RESULT {'PASS' if code == 0 else 'FAIL'}  ({_checks} 项)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
