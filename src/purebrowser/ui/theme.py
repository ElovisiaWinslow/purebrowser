"""PureBrowser 主题系统：语义色 + QSS 生成。

风格参考 macOS Ventura，纯 QSS 实现（不含原生模糊）。
不要在 theme.py 里读取设置文件：主题由调用方（app.py）从 Settings 读出后传入。
"""
from __future__ import annotations

from dataclasses import dataclass
from string import Template

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import QApplication


@dataclass(frozen=True)
class Theme:
    name: str
    window: str       # 窗口背景
    chrome: str       # 工具栏 / 标签栏背景
    text: str         # 主文字
    subtext: str      # 次文字
    accent: str       # 强调色
    border: str       # 边框
    hover: str        # hover 背景
    danger: str       # 危险操作（清除）
    on_accent: str    # 强调色上的文字
    radius: int = 8   # 组件圆角
    panel: int = 10   # 面板圆角


LIGHT = Theme(
    name="light",
    window="#ECECEC",
    chrome="#F5F5F7",
    text="#1D1D1F",
    subtext="#86868B",
    accent="#007AFF",
    border="#D2D2D7",
    hover="#E5E5E7",
    danger="#FF3B30",
    on_accent="#FFFFFF",
)

DARK = Theme(
    name="dark",
    window="#1E1E1E",
    chrome="#2C2C2E",
    text="#F5F5F7",
    subtext="#98989D",
    accent="#0A84FF",
    border="#3A3A3C",
    hover="#3A3A3C",
    danger="#FF453A",
    on_accent="#FFFFFF",
)


def detect_system_theme() -> str:
    """读取系统配色方案，返回 'light' | 'dark'。无法判断时按 light。"""
    app = QGuiApplication.instance()
    if app is not None:
        hints = app.styleHints()
        if hints is not None:
            scheme = hints.colorScheme()
            if scheme == Qt.ColorScheme.Dark:
                return "dark"
            if scheme == Qt.ColorScheme.Light:
                return "light"
    return "light"


def resolve_theme(setting: str) -> Theme:
    """把 'system' | 'light' | 'dark' 解析为具体 Theme。未知值按 system。"""
    if setting == "light":
        return LIGHT
    if setting == "dark":
        return DARK
    return DARK if detect_system_theme() == "dark" else LIGHT


_QSS_TEMPLATE = Template(
    """
QMainWindow, QDialog { background: $window; color: $text; }
QWidget { color: $text; }

QToolTip {
    background: $chrome; color: $text;
    border: 1px solid $border; border-radius: $radius; padding: 4px 8px;
}

QToolBar {
    background: $chrome; border: 0;
    border-bottom: 1px solid $border;
    padding: 4px 6px; spacing: 2px;
}
QToolBar::separator { background: $border; width: 1px; margin: 4px 6px; }
QToolBar QToolButton {
    background: transparent; border: 0;
    border-radius: $radius; padding: 4px 8px; color: $text;
}
QToolButton { color: $text; border-radius: $radius; }
QToolButton:hover { background: $hover; }
QToolButton:pressed, QToolButton:checked { background: $border; }
QToolButton::menu-indicator { image: none; }

QTabWidget::pane { border: 0; background: $window; }
QTabBar { background: $chrome; qproperty-drawBase: 0; }
QTabBar::tab {
    background: transparent; color: $subtext; border: 0;
    border-top-left-radius: $panel; border-top-right-radius: $panel;
    padding: 6px 14px; margin: 4px 2px 0 2px; min-width: 90px;
}
QTabBar::tab:selected { background: $window; color: $text; }
QTabBar::tab:hover:!selected { background: $hover; }
QTabBar::close-button { background: transparent; }

QLineEdit {
    background: $window; color: $text;
    border: 1px solid $border; border-radius: $radius; padding: 5px 10px;
    selection-background-color: $accent; selection-color: $on_accent;
}
QLineEdit:hover { border-color: $subtext; }
QLineEdit:focus { border: 1px solid $accent; }

QMenu {
    background: $chrome; color: $text;
    border: 1px solid $border; border-radius: $panel; padding: 6px;
}
QMenu::item { padding: 6px 24px 6px 12px; border-radius: $radius; background: transparent; }
QMenu::item:selected { background: $accent; color: $on_accent; }
QMenu::item:disabled { color: $subtext; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }

QStatusBar { background: $chrome; color: $subtext; border-top: 1px solid $border; }
QStatusBar::item { border: 0; }
QStatusBar QLabel { color: $subtext; }

QProgressBar {
    background: $window; color: $subtext;
    border: 1px solid $border; border-radius: $radius;
    text-align: center; max-height: 10px;
}
QProgressBar::chunk { background: $accent; border-radius: $radius; }

QAbstractItemView {
    background: $chrome; color: $text;
    border: 1px solid $border; border-radius: $panel; outline: 0;
    selection-background-color: $accent; selection-color: $on_accent;
}
QAbstractItemView::item { padding: 4px 8px; border-radius: $radius; }
QAbstractItemView::item:hover { background: $hover; }
QAbstractItemView::item:selected { background: $accent; color: $on_accent; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: $subtext; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 5px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: $subtext; }
QScrollBar::add-line, QScrollBar::sub-line {
    width: 0; height: 0; background: none; border: none;
}
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
"""
)


def build_qss(theme: Theme) -> str:
    """根据 Theme 生成完整 QSS 字符串。"""
    values = {
        "window": theme.window,
        "chrome": theme.chrome,
        "text": theme.text,
        "subtext": theme.subtext,
        "accent": theme.accent,
        "border": theme.border,
        "hover": theme.hover,
        "danger": theme.danger,
        "on_accent": theme.on_accent,
        "radius": str(theme.radius),
        "panel": str(theme.panel),
    }
    return _QSS_TEMPLATE.substitute(values)


def apply(app: QApplication, theme: Theme) -> None:
    """把主题应用到 QApplication：设置调色板 + 全局 QSS。"""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.window))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.chrome))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(theme.subtext))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.chrome))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.chrome))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.on_accent))
    app.setPalette(palette)
    app.setStyleSheet(build_qss(theme))
