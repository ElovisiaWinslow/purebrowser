"""PureBrowser 全屏快捷键/harness 测试（不联网，不打开真实站点）。

只启动 MainWindow，直接调用窗口方法，覆盖四条路径::

    1  最大化   enter_fullscreen()   -> exit_fullscreen()    -> 最大化
    2  最大化   _toggle_fullscreen() -> _toggle_fullscreen() -> 最大化
    3  窗口化   _toggle_fullscreen() -> _toggle_fullscreen() -> 窗口化
    4  最大化   enter_fullscreen()   -> _toggle_fullscreen() -> 最大化
       （第 4 条验证"视频全屏期间按 F11"走的是退出逻辑，而不是重复进入）

编码这些快捷键的行为:
    F11 -> MainWindow._toggle_fullscreen()
    Esc -> MainWindow._exit_fullscreen()

与 tools/fullscreen_test.py 的区别:
    不加载任何 URL、不注入 JS、不需要用户激活、不需要网络。
    仅验证 MainWindow 层的原生 Win32 全屏状态机 + 无中间态几何。

用法::

    .venv\\Scripts\\python.exe tools\\fullscreen_harness_test.py

退出码:
    0 = 全部通过
    1 = 失败
"""
from __future__ import annotations

import ctypes
import os
import sys
import tempfile
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

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from purebrowser.ui.window import MainWindow

SAMPLE_INTERVAL_MS = 5
STEP_SETTLE_MS = 600
FINAL_SETTLE_MS = 400
HARD_TIMEOUT_MS = 90000

# ---------------------------------------------------------------------------
# 原生窗口几何（仅测试断言用，不修改被测代码）
# ---------------------------------------------------------------------------
IS_WINDOWS = os.name == "nt"
if IS_WINDOWS:
    # 必须用独立的 WinDLL 实例：ctypes.windll.user32 是带缓存的单例，
    # 设置 argtypes 会改写其它模块（含 window.py）同一批函数对象的签名，
    # 进而在原生进入全屏时触发崩溃。
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


def emit(line: str) -> None:
    print(line, flush=True)


def rect_close(a, b, tol: int = 2) -> bool:
    return all(abs(int(x) - int(y)) <= tol for x, y in zip(a, b))


class HarnessTest:
    def __init__(self, app: QApplication, win: MainWindow):
        self.app = app
        self.win = win
        self.results: list[tuple[str, bool, str]] = []
        self.samples: list[tuple] = []
        self.sampling = False
        self.si = -1
        self.finished = False

        self.sampler = QTimer()
        self.sampler.setInterval(SAMPLE_INTERVAL_MS)
        self.sampler.timeout.connect(self._sample)

        # (名称, 起始状态, 动作序列, 期望最大化)
        self.scenarios = [
            ("path1 最大化 -> enter_fullscreen -> exit_fullscreen   -> 最大化",
             "maximized", ["enter_fullscreen", "exit_fullscreen"], True),
            ("path2 最大化 -> F11 -> F11                            -> 最大化",
             "maximized", ["_toggle_fullscreen", "_toggle_fullscreen"], True),
            ("path3 窗口化 -> F11 -> F11                            -> 窗口化",
             "windowed", ["_toggle_fullscreen", "_toggle_fullscreen"], False),
            ("path4 最大化 -> enter_fullscreen -> F11               -> 最大化",
             "maximized", ["enter_fullscreen", "_toggle_fullscreen"], True),
        ]

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
        emit(f"[INFO] 显示器: {self._monitor_rect()}  (物理像素)")
        self.win.activateWindow()
        self.win.raise_()
        self._next_scenario()

    def _next_scenario(self) -> None:
        if self.si + 1 >= len(self.scenarios):
            self._finish()
            return
        self.si += 1
        name, init, actions, expect_max = self.scenarios[self.si]
        self.current_name = name
        self.actions = actions
        self.expect_max = expect_max
        emit(f"[INFO] {name}")
        self._setup_state(init)
        QTimer.singleShot(800, self._begin_actions)

    def _setup_state(self, kind: str) -> None:
        self.win.showNormal()
        self.win.resize(900, 640)
        if kind == "maximized":
            self.win.showMaximized()
        self._update()

    def _begin_actions(self) -> None:
        self.start_rect = self._rect()
        self.samples = []
        self.sampling = True
        self.sampler.start()
        self.action_index = 0
        self._run_next_action()

    def _run_next_action(self) -> None:
        if self.action_index >= len(self.actions):
            QTimer.singleShot(FINAL_SETTLE_MS, self._verify)
            return
        action = self.actions[self.action_index]
        self.action_index += 1
        getattr(self.win, action)()
        QTimer.singleShot(STEP_SETTLE_MS, self._run_next_action)

    def _verify(self) -> None:
        self.sampling = False
        self.sampler.stop()
        monitor = self._monitor_rect()
        final = self._rect()
        zoomed = self._zoomed()

        problems = []
        if zoomed != self.expect_max:
            problems.append(f"IsZoomed={zoomed} 期望 {self.expect_max}")
        if not rect_close(final, self.start_rect):
            problems.append(f"最终几何 {final} != 起始几何 {self.start_rect}")
        if self.win._is_fullscreen:
            problems.append("_is_fullscreen 未复位")
        if not any(rect_close(r, monitor) for r in self.samples):
            problems.append("全程未观察到进入全屏（未采样到显示器矩形）")
        bad = self._first_intermediate(self.samples, [self.start_rect, monitor])
        if bad is not None:
            problems.append(
                f"出现中间态几何 rect={bad}（allowed={self.start_rect} 或 {monitor}）"
            )

        if problems:
            self._fail("; ".join(problems))
        else:
            self._pass(
                f"start_rect={self.start_rect} final_rect={final} "
                f"zoomed={zoomed} samples={len(self.samples)}"
            )
        self._next_scenario()

    # ---------- 工具 ----------
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

    def _update(self) -> None:
        self.app.processEvents()


def main() -> int:
    if not IS_WINDOWS:
        emit("[SKIP] 该测试依赖 Windows 原生窗口 API")
        return 2

    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        data_dir = Path(tempfile.mkdtemp(prefix="pb_fs_harness_"))
        win = MainWindow(data_dir)
        win.resize(900, 640)
        win.show()
        win.activateWindow()
        win.raise_()
        runner = HarnessTest(app, win)
        QTimer.singleShot(300, runner.start)
        return app.exec()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
