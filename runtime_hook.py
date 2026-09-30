# runtime_hook.py — PyInstaller 打包后的运行时环境设置
# 目的：让 Qt6 在打包目录内找到插件和 QtWebEngineProcess.exe
import os
import sys

base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))

os.environ["QT_PLUGIN_PATH"] = os.path.join(base, "plugins")
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.join(base, "plugins", "platforms")
os.environ["QTWEBENGINEPROCESS_PATH"] = os.path.join(base, "QtWebEngineProcess.exe")
os.environ["QTWEBENGINE_RESOURCES_PATH"] = os.path.join(base, "resources")
os.environ["QTWEBENGINE_LOCALES_PATH"] = os.path.join(base, "translations", "qtwebengine_locales")
