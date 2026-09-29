"""PureBrowser 冒烟测试。每次改动后运行。

用法: python tools/smoke_test.py
"""
import sys
from pathlib import Path

FAILS = []


def check(name, fn):
    try:
        fn()
        print(f"[OK]   {name}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        FAILS.append(name)


def check_qt_version():
    from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
    assert QT_VERSION_STR == "6.7.3", f"Qt version is {QT_VERSION_STR}, expected 6.7.3"
    assert PYQT_VERSION_STR == "6.7.1", f"PyQt version is {PYQT_VERSION_STR}, expected 6.7.1"


def check_webengine_import():
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa
    from PyQt6.QtWebEngineCore import QWebEnginePage  # noqa


def check_purebrowser_import():
    import purebrowser
    from purebrowser.ui import window, tab, urlbar  # noqa
    from purebrowser.core import profile, interceptor  # noqa


def check_no_qt6_official():
    """确认没有 pip 安装的官方 Qt6 包覆盖自编译版本。"""
    import importlib.metadata as md
    bad = []
    for name in ("PyQt6-Qt6", "PyQt6-WebEngine-Qt6"):
        try:
            md.version(name)
            bad.append(name)
        except md.PackageNotFoundError:
            pass
    assert not bad, f"发现官方 Qt6 包: {bad}。这会覆盖自编译 Qt。"


def check_data_dir():
    from purebrowser.core.locations import get_data_dir
    d = get_data_dir()
    assert d.exists(), f"数据目录不存在: {d}"


def main() -> int:
    print("=" * 50)
    print("PureBrowser smoke test")
    print("=" * 50)

    check("Qt 版本", check_qt_version)
    check("QtWebEngine 导入", check_webengine_import)
    check("PureBrowser 导入", check_purebrowser_import)
    check("无官方 Qt6 覆盖", check_no_qt6_official)
    check("数据目录", check_data_dir)

    print("=" * 50)
    if FAILS:
        print(f"失败: {len(FAILS)} 项")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())