"""启动时的会话恢复提示卡片。

浏览器在有可恢复会话时，于窗口顶部中央弹出一张小卡片，让用户自己选择
是否恢复上次关闭的标签页（恢复 / 不用了 / ×）。纯 Qt 控件 + QSS，不弹原生
对话框，风格与浏览器一致。
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

WIDTH = 360


class SessionPrompt(QWidget):
    restore = pyqtSignal()
    skip = pyqtSignal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.setObjectName("sessionPrompt")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(WIDTH)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 12, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(6)
        self._title = QLabel("恢复上次会话？", self)
        self._title.setObjectName("sessionPromptTitle")
        top.addWidget(self._title, 1)
        self._close = QToolButton(self)
        self._close.setObjectName("sessionCloseBtn")
        self._close.setText("\u00D7")
        self._close.setToolTip("不恢复")
        self._close.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close.clicked.connect(self._on_skip)
        top.addWidget(self._close, 0)
        root.addLayout(top)

        self._desc = QLabel("", self)
        self._desc.setObjectName("sessionPromptDesc")
        self._desc.setWordWrap(True)
        root.addWidget(self._desc)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addStretch(1)
        self._skip = QToolButton(self)
        self._skip.setObjectName("sessionSkipBtn")
        self._skip.setText("不用了")
        self._skip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._skip.clicked.connect(self._on_skip)
        row.addWidget(self._skip)
        self._restore = QToolButton(self)
        self._restore.setObjectName("sessionRestoreBtn")
        self._restore.setText("恢复")
        self._restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restore.clicked.connect(self._on_restore)
        row.addWidget(self._restore)
        root.addLayout(row)

        self._apply_style(theme)

    def set_count(self, n: int) -> None:
        self._desc.setText(f"上次关闭时有 {n} 个标签页，是否重新打开？")

    def show_card(self) -> None:
        parent = self.parentWidget()
        self.adjustSize()
        if parent is not None:
            x = max(8, (parent.width() - self.width()) // 2)
        else:
            x = 8
        self.move(x, 16)
        self.show()
        self.raise_()

    def _on_restore(self) -> None:
        self.hide()
        self.restore.emit()

    def _on_skip(self) -> None:
        self.hide()
        self.skip.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._on_skip()
            return
        super().keyPressEvent(event)

    def _apply_style(self, theme) -> None:
        t = theme
        self.setStyleSheet(
            f"#sessionPrompt {{ background: {t.chrome};"
            f" border: 1px solid {t.border}; border-radius: 10px; }}"
            f"#sessionPromptTitle {{ color: {t.text}; font-size: 14px; font-weight: 600; }}"
            f"#sessionPromptDesc {{ color: {t.subtext}; font-size: 12px; }}"
            f"#sessionRestoreBtn {{ background: {t.accent}; color: {t.on_accent};"
            " border: 0; border-radius: 6px; padding: 5px 18px;"
            " font-size: 13px; font-weight: 600; }"
            f"#sessionRestoreBtn:hover {{ background: {t.text}; }}"
            f"#sessionSkipBtn {{ background: transparent; color: {t.subtext};"
            " border: 0; border-radius: 6px; padding: 5px 12px; font-size: 13px; }"
            f"#sessionSkipBtn:hover {{ background: {t.hover}; color: {t.text}; }}"
            f"#sessionCloseBtn {{ background: transparent; color: {t.subtext};"
            " border: 0; border-radius: 6px; min-width: 22px; min-height: 22px;"
            " font-size: 15px; }"
            f"#sessionCloseBtn:hover {{ background: {t.hover}; color: {t.text}; }}"
        )
