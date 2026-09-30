# PureBrowser.spec
# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

PROJECT = Path(r"D:\PythonProject\purebrowser")
SRC = PROJECT / "src"
QT6_DIR = Path(r"D:\develop\Qt6-custom")
RESOURCES = PROJECT / "resources"

# --- Qt6 运行时（自编译版，PyQt6 包里没有，必须手动收） ---
qt6_bin = QT6_DIR / "bin"

# 所有 DLL（Qt6 核心 + QtWebEngine）
binaries_qt6 = [(str(p), ".") for p in qt6_bin.glob("*.dll")]
# QtWebEngineProcess.exe 必须
binaries_qt6.append((str(qt6_bin / "QtWebEngineProcess.exe"), "."))

# Qt6 资源（QtWebEngine 必需：icudtl.dat / *.pak / v8_context_snapshot.bin）
datas_qt6 = []
qt6_res = QT6_DIR / "resources"
if qt6_res.exists():
    for p in qt6_res.iterdir():
        if p.is_file():
            datas_qt6.append((str(p), "resources"))
        elif p.is_dir():
            datas_qt6.append((str(p), f"resources/{p.name}"))

# Qt6 插件（只挑运行必需的）
qt6_plugins = QT6_DIR / "plugins"
for name in ["platforms", "imageformats", "styles", "tls",
             "iconengines", "networkinformation"]:
    sub = qt6_plugins / name
    if sub.exists():
        datas_qt6.append((str(sub), f"plugins/{name}"))

# QtWebEngine 本地化（Chromium 的 .pak）
qt6_locales = QT6_DIR / "translations" / "qtwebengine_locales"
if qt6_locales.exists():
    datas_qt6.append((str(qt6_locales), "translations/qtwebengine_locales"))

# --- 项目资源（HTML / CSS / 图标） ---
datas_project = [(str(RESOURCES), "resources")]

# --- 分析 ---
a = Analysis(
    [str(SRC / "purebrowser" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=binaries_qt6,
    datas=datas_qt6 + datas_project,
    hiddenimports=[
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebChannel",
        "PyQt6.QtQuick",
        "PyQt6.QtQml",
        "PyQt6.QtNetwork",
        "PyQt6.QtPrintSupport",
        "PyQt6.QtSvg",
        "PyQt6.QtSql",
        "PyQt6.QtOpenGL",
        "PyQt6.QtOpenGLWidgets",
    ],
    runtime_hooks=[str(PROJECT / "runtime_hook.py")],
    excludes=[],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PureBrowser",
    console=False,
    icon=str(RESOURCES / "purebrowser.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="PureBrowser",
)
