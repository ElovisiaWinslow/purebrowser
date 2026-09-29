"""PureBrowser 全屏端到端测试（真实站点，走 Fullscreen API 完整链路）。

验证链路::

    document.documentElement.requestFullscreen()
        -> 浏览器授予用户激活后发出 QWebEnginePage.fullScreenRequested
        -> PurePage._handle_fullscreen (tab.py)
        -> Tab.fullscreen_toggled
        -> MainWindow._on_fullscreen_toggled -> _native_enter_fullscreen (window.py)

    document.exitFullscreen() 反向走同一条链路。

用 5ms 采样窗口几何，断言进入/退出过程中不出现"窗口化中间态"。

用法::

    .venv\\Scripts\\python.exe tools\\fullscreen_test.py

可用环境变量覆盖目标页（默认一个公开 B 站视频页）::

    PUREBROWSER_FULLSCREEN_URL=https://www.bilibili.com/video/BVxxxxxxxxxx

退出码:
    0 = 全部通过
    1 = 失败（功能 bug / 页面策略变化）
    2 = 跳过（网络不可达）
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
import time
import traceback
from ctypes import wintypes
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

from PyQt6.QtCore import QPoint, QTimer, Qt, QUrl
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from purebrowser.ui.window import MainWindow

DEFAULT_URL = "https://www.bilibili.com/video/BV1xx411c7mD"
TARGET_URL = os.environ.get("PUREBROWSER_FULLSCREEN_URL", DEFAULT_URL)

LOAD_TIMEOUT_MS = 35000
STEP_TIMEOUT_MS = 5000
SAMPLE_INTERVAL_MS = 5
HARD_TIMEOUT_MS = 150000

# ---------------------------------------------------------------------------
# 原生窗口几何（仅测试断言用，不修改被测代码）
# ---------------------------------------------------------------------------
IS_WINDOWS = os.name == "nt"
if IS_WINDOWS:
    # 必须用独立的 WinDLL 实例：ctypes.windll.user32 是带缓存的单例，
    # 在测试里设置 argtypes 会改写 window.py 中同一批函数对象的签名。
    _user32 = ctypes.WinDLL("user32")

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetWindowRect.restype = wintypes.BOOL
    _user32.IsZoomed.argtypes = [wintypes.HWND]
    _user32.IsZoomed.restype = wintypes.BOOL
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.MonitorFromWindow.restype = ctypes.c_void_p
    _user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFO)]
    _user32.GetMonitorInfoW.restype = wintypes.BOOL

# ---------------------------------------------------------------------------
# 注入的 JS
# ---------------------------------------------------------------------------
JS_INJECT_OVERLAY = """
(function(){
  var d = document.getElementById('__pbfs_overlay__');
  if (!d) {
    d = document.createElement('div');
    d.id = '__pbfs_overlay__';
    document.documentElement.appendChild(d);
  }
  d.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;' +
                    'z-index:2147483647;background:transparent;pointer-events:auto;';
  return true;
})()
"""

JS_REMOVE_OVERLAY = """
(function(){
  var d = document.getElementById('__pbfs_overlay__');
  if (d) { d.remove(); }
  return true;
})()
"""

JS_REQUEST_FS = """
(function(){
  window.__pbfs_err = null;
  try {
    var p = document.documentElement.requestFullscreen();
    if (p && p.catch) { p.catch(function(e){ window.__pbfs_err = String(e); }); }
    return 'requested';
  } catch (e) { window.__pbfs_err = String(e); return 'threw:' + String(e); }
})()
"""

JS_EXIT_FS = """
(function(){
  try {
    if (document.fullscreenElement) {
      var p = document.exitFullscreen();
      if (p && p.catch) { p.catch(function(e){ window.__pbfs_err = String(e); }); }
    }
    return true;
  } catch (e) { return 'threw:' + String(e); }
})()
"""

JS_STATE = """
JSON.stringify({
  fe: document.fullscreenElement ? (document.fullscreenElement.tagName || 'element') : null,
  enabled: document.fullscreenEnabled,
  err: window.__pbfs_err || null
})
"""


def emit(line: str) -> None:
    print(line, flush=True)


def rect_close(a, b, tol: int = 2) -> bool:
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a, b))


class FullscreenTest:
    def __init__(self, app: QApplication, win: MainWindow):
        self.app = app
        self.win = win
        self.tab = win._current()
        self.view = self.tab.view
        self.page = self.view.page()

        self.results: list[tuple[str, bool, str]] = []
        self.requests: list[bool] = []
        self.samples: list[tuple] = []
        self.sampling = False

        self.page.fullScreenRequested.connect(
            lambda r: self.requests.append(r.toggleOn())
        )

        self.sampler = QTimer()
        self.sampler.setInterval(SAMPLE_INTERVAL_MS)
        self.sampler.timeout.connect(self._sample)

        self.scenarios = [
            ("path1 窗口化 -> requestFullscreen -> exitFullscreen -> 窗口化", False),
            ("path2 最大化 -> requestFullscreen -> exitFullscreen -> 最大化", True),
        ]
        self.si = -1
        self.load_started = False
        self.load_done = False
        self.finished = False

        QTimer.singleShot(HARD_TIMEOUT_MS, self._hard_timeout)

    # ---------- 原生几何 ----------
    def _hwnd(self):
        return wintypes.HWND(int(self.win.winId()))

    def _rect(self):
        r = wintypes.RECT()
        _user32.GetWindowRect(self._hwnd(), ctypes.byref(r))
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def _zoomed(self) -> bool:
        return bool(_user32.IsZoomed(self._hwnd()))

    def _monitor_rect(self):
        mon = _user32.MonitorFromWindow(self._hwnd(), 2)  # MONITOR_DEFAULTTONEAREST
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if mon and _user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            r = info.rcMonitor
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        raise RuntimeError("GetMonitorInfoW 失败")

    def _sample(self) -> None:
        if self.sampling:
            self.samples.append(self._rect())

    # ---------- 流程 ----------
    def start(self) -> None:
        emit(f"[INFO] 目标页: {TARGET_URL}")
        emit(f"[INFO] 显示器: {self._monitor_rect()}  (物理像素)")
        self.win.activateWindow()
        self.win.raise_()
        self.view.loadFinished.connect(self._on_load_finished)
        self.load_started = True
        self.view.load(QUrl(TARGET_URL))
        QTimer.singleShot(LOAD_TIMEOUT_MS, self._on_load_timeout)

    def _on_load_finished(self, ok: bool) -> None:
        if self.load_done:
            return
        self.load_done = True
        if not ok:
            self._skip("网络不可达（loadFinished=False）")
            return
        emit("[INFO] 页面加载完成，等待播放器/脚本初始化")
        QTimer.singleShot(1500, self._next_scenario)

    def _on_load_timeout(self) -> None:
        if not self.load_done:
            self.load_done = True
            self._skip(f"加载超时（{LOAD_TIMEOUT_MS} ms 内未完成）")

    def _skip(self, reason: str) -> None:
        emit(f"[SKIP] {reason}")
        emit("[SKIP] 网络不可达，跳过真实站点测试")
        self._shutdown(2)

    def _shutdown(self, code: int) -> None:
        # QtWebEngine 在进程退出时偶发 access violation（0xC0000005）：
        # 先关闭窗口，让 MainWindow.closeEvent 释放 page / blocker / 连接，再退出。
        self.finished = True
        QTimer.singleShot(0, self._close_window)
        QTimer.singleShot(250, lambda: self.app.exit(code))

    def _close_window(self) -> None:
        try:
            self.win.close()
        except Exception:  # noqa: BLE001
            pass

    def _next_scenario(self) -> None:
        if self.si + 1 >= len(self.scenarios):
            self._finish()
            return
        self.si += 1
        name, expect_max = self.scenarios[self.si]
        self.current_name = name
        self.expect_max = expect_max
        emit(f"[INFO] {name}")
        self._setup_state("maximized" if expect_max else "windowed")
        QTimer.singleShot(800, self._grant_activation)

    def _setup_state(self, kind: str) -> None:
        self.win.showNormal()
        self.win.resize(900, 640)
        if kind == "maximized":
            self.win.showMaximized()
        self._update()

    def _grant_activation(self) -> None:
        # Fullscreen API 需要瞬时用户激活。runJavaScript 不产生激活，
        # 因此向 web 内容的 focusProxy 发一个合成鼠标点击；
        # 先注入透明覆盖层，避免点中页面上的真实链接/按钮。
        self.win.activateWindow()
        self.view.setFocus()
        self.page.runJavaScript(JS_INJECT_OVERLAY)
        QTimer.singleShot(120, self._do_click)

    def _do_click(self) -> None:
        fp = self.view.focusProxy() or self.view
        QTest.mouseClick(
            fp,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            QPoint(max(1, fp.width() // 2), max(1, fp.height() // 2)),
        )
        QTimer.singleShot(150, self._after_click)

    def _after_click(self) -> None:
        self.page.runJavaScript(JS_REMOVE_OVERLAY)
        QTimer.singleShot(100, self._check_enabled)

    def _check_enabled(self) -> None:
        self.page.runJavaScript("document.fullscreenEnabled", self._on_enabled)

    def _on_enabled(self, enabled) -> None:
        if not enabled:
            self._fail("document.fullscreenEnabled=false（FullScreenSetting 未生效或页面策略禁止）")
            self._next_scenario()
            return
        self._enter()

    def _enter(self) -> None:
        self.requests.clear()
        self.samples.clear()
        self.enter_start = self._rect()
        self.sampling = True
        self.sampler.start()
        self.page.runJavaScript(JS_REQUEST_FS)
        self._wait_until(
            lambda: self.win._is_fullscreen,
            self._on_entered,
            STEP_TIMEOUT_MS,
            "进入全屏超时：fullScreenRequested 未触发或窗口未进入全屏",
        )

    def _on_entered(self) -> None:
        # 给原生 SetWindowPos 收尾
        QTimer.singleShot(150, self._verify_enter)

    def _verify_enter(self) -> None:
        self.sampling = False
        monitor = self._monitor_rect()
        cur = self._rect()
        if not rect_close(cur, monitor):
            self._fail(f"进入全屏后几何不是显示器全屏: cur={cur} monitor={monitor}")
            self._next_scenario()
            return
        self.page.runJavaScript(JS_STATE, self._on_enter_state)

    def _on_enter_state(self, raw) -> None:
        import json

        state = json.loads(raw) if raw else {}
        if not state.get("fe"):
            self._fail(f"窗口已全屏但页面 fullscreenElement 为空: {state}")
            self._next_scenario()
            return
        if True not in self.requests:
            self._fail("未观测到 fullScreenRequested(toggleOn=True)")
            self._next_scenario()
            return
        monitor = self._monitor_rect()
        bad = self._first_intermediate(self.samples, [self.enter_start, monitor])
        if bad is not None:
            self._fail(f"进入全屏出现中间态几何 rect={bad}（start={self.enter_start} fs={monitor}）")
            self._next_scenario()
            return
        # 进入通过，准备退出
        self.samples.clear()
        self.sampling = True
        self.page.runJavaScript(JS_EXIT_FS)
        self._wait_until(
            lambda: not self.win._is_fullscreen,
            self._on_exited,
            STEP_TIMEOUT_MS,
            "退出全屏超时：窗口未回到非全屏",
        )

    def _on_exited(self) -> None:
        QTimer.singleShot(200, self._verify_exit)

    def _verify_exit(self) -> None:
        self.sampling = False
        final = self._rect()
        zoomed = self._zoomed()
        monitor = self._monitor_rect()

        problems = []
        if zoomed != self.expect_max:
            problems.append(f"IsZoomed={zoomed} 期望 {self.expect_max}")
        bad = self._first_intermediate(self.samples, [monitor, final])
        if bad is not None:
            problems.append(
                f"退出全屏出现中间态几何 rect={bad}（fs={monitor} final={final}）"
            )
        if False not in self.requests:
            problems.append("未观测到 fullScreenRequested(toggleOn=False)")

        if problems:
            self._fail("; ".join(problems))
        else:
            self._pass(
                f"final_rect={final} zoomed={zoomed} "
                f"req={[('on' if x else 'off') for x in self.requests]}"
            )
        self._next_scenario()

    # ---------- 工具 ----------
    def _wait_until(self, cond, on_ok, timeout_ms: int, timeout_msg: str) -> None:
        deadline = time.monotonic() + timeout_ms / 1000.0

        def tick():
            try:
                if cond():
                    on_ok()
                    return
            except Exception as exc:  # noqa: BLE001
                self._fail(f"等待过程异常: {exc}")
                self._next_scenario()
                return
            if time.monotonic() > deadline:
                self._fail(timeout_msg)
                self._next_scenario()
                return
            QTimer.singleShot(60, tick)

        QTimer.singleShot(0, tick)

    @staticmethod
    def _first_intermediate(samples, allowed):
        for r in samples:
            if not any(rect_close(r, a) for a in allowed):
                return r
        return None

    def _pass(self, detail: str = "") -> None:
        emit(f"[PASS] {self.current_name}" + (f"  ({detail})" if detail else ""))
        self.results.append((self.current_name, True, detail))

    def _fail(self, reason: str) -> None:
        emit(f"[FAIL] {self.current_name}  -- {reason}")
        self.results.append((self.current_name, False, reason))

    def _finish(self) -> None:
        emit("=" * 60)
        passed = sum(1 for _, ok, _ in self.results if ok)
        total = len(self.scenarios)
        emit(f"RESULT {passed}/{total} passed")
        self._shutdown(0 if passed == total else 1)

    def _hard_timeout(self) -> None:
        if self.finished:
            return
        emit(f"[FAIL] 硬超时（{HARD_TIMEOUT_MS} ms）")
        emit(f"RESULT 0/{len(self.scenarios)} passed")
        self._shutdown(1)

    def _update(self) -> None:
        self.app.processEvents()


def main() -> int:
    if not IS_WINDOWS:
        emit("[SKIP] 该测试依赖 Windows 原生窗口 API")
        return 2

    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        data_dir = Path(tempfile.mkdtemp(prefix="pb_fs_e2e_"))
        win = MainWindow(data_dir)
        win.resize(900, 640)
        win.show()
        win.activateWindow()
        win.raise_()
        runner = FullscreenTest(app, win)
        QTimer.singleShot(300, runner.start)
        return app.exec()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
