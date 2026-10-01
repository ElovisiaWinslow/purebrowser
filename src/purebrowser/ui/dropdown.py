"""自绘不透明可滚动下拉面板（历史 / 书签 / 下载共用）。

替代原 QMenu 下拉：
- 非 layered（不透明自绘）——避免 QMenu 的逐帧 alpha 合成；
- QScrollArea 可上下滚动，内容过长时出现滚动条；
- 分组标题 + 富行；
- 支持原地实时刷新（下载进度）。
与右键 ContextMenu 同源。
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

ROW_W = 360
PANEL_W = ROW_W + 26          # 行宽 + 左右内边距 + 滚动条
MAX_H_RATIO = 0.72
HEADER_H = 40


class _SectionHeader(QLabel):
    def __init__(self, theme, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("ddSection")
        self.setFixedHeight(24)
        self.setStyleSheet(
            f"#ddSection {{ color: {theme.subtext}; font-size: 11px;"
            f" font-weight: 600; padding: 6px 2px 2px 2px; }}"
        )


class DropdownPanel(QWidget):
    def __init__(self, theme, parent=None):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._theme = theme
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedWidth(PANEL_W)

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        self._header = QWidget(self)
        self._header.setObjectName("ddHeader")
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(12, 5, 8, 5)
        hl.setSpacing(6)
        self._title = QLabel(self._header)
        self._title.setObjectName("ddTitle")
        hl.addWidget(self._title, 1)
        self._action = QToolButton(self._header)
        self._action.setObjectName("ddAction")
        self._action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action.setAutoRaise(True)
        self._action.setVisible(False)
        hl.addWidget(self._action, 0)
        root.addWidget(self._header)

        self._body = QWidget()
        self._body.setObjectName("ddBody")
        self._body.setAutoFillBackground(True)
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(8, 4, 2, 8)
        self._body_lay.setSpacing(1)
        self._body_lay.addStretch(1)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("ddScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setWidget(self._body)
        self._scroll.viewport().setAutoFillBackground(True)
        root.addWidget(self._scroll, 1)

        self._rows: list = []
        # 滚动时行会从光标下方滑走但不触发 Enter/Leave，这里重新对账高亮。
        self._scroll.verticalScrollBar().valueChanged.connect(self._resync_hover)
        # 兜底：面板可见期间，光标移动时对所有行重新对账（仅移动才做事，开销极小）。
        self._last_cursor = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(150)
        self._hover_timer.timeout.connect(self._hover_tick)

        self._apply_style()

    def _resync_hover(self) -> None:
        for row in self._rows:
            sync = getattr(row, "_sync_hover", None)
            if sync is not None:
                sync()

    def _hover_tick(self) -> None:
        pos = QCursor.pos()
        if pos == self._last_cursor:
            return
        self._last_cursor = pos
        self._resync_hover()

    def hideEvent(self, event) -> None:
        self._hover_timer.stop()
        for row in self._rows:
            clear = getattr(row, "_set_hovered", None)
            if clear is not None:
                clear(False)
        super().hideEvent(event)

    # ---------- content ----------
    def set_header(self, title, action_text=None, action_cb=None) -> None:
        self._title.setText(title or "")
        if action_text and action_cb is not None:
            self._action.setText(action_text)
            try:
                self._action.clicked.disconnect()
            except TypeError:
                pass
            self._action.clicked.connect(action_cb)
            self._action.setVisible(True)
        else:
            self._action.setVisible(False)

    def set_sections(self, sections) -> None:
        """sections: [(标题或 None, [MenuRow, ...]), ...]"""
        while self._body_lay.count() > 1:
            item = self._body_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._rows = []
        idx = 0
        for title, rows in sections:
            if title:
                self._body_lay.insertWidget(idx, _SectionHeader(self._theme, title))
                idx += 1
            for row in rows:
                self._body_lay.insertWidget(idx, row)
                self._rows.append(row)
                idx += 1
        self._body_lay.activate()

    def rows(self) -> list:
        return list(self._rows)

    # ---------- open ----------
    def open_below(self, anchor: QWidget) -> None:
        self._body.adjustSize()
        content_h = self._body.sizeHint().height()
        screen = anchor.screen() or QApplication.primaryScreen()
        avail_h = int(screen.availableGeometry().height() * MAX_H_RATIO)
        total_h = min(content_h + HEADER_H + 8, avail_h)
        self._scroll.setFixedHeight(max(60, total_h - HEADER_H - 2))
        self.setFixedHeight(total_h)

        bl = anchor.mapToGlobal(QPoint(0, anchor.height()))
        x = bl.x() + anchor.width() - self.width()
        y = bl.y() + 4
        g = screen.availableGeometry()
        x = min(max(x, g.left() + 4), g.right() - self.width() - 3)
        y = min(max(y, g.top() + 4), g.bottom() - self.height() - 3)
        self.move(x, y)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        self._last_cursor = None
        self._hover_timer.start()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)

    # ---------- paint ----------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self._theme.chrome))
        p.setPen(QColor(self._theme.border))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _apply_style(self) -> None:
        t = self._theme
        pal = self._body.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(t.chrome))
        self._body.setPalette(pal)
        vpal = self._scroll.viewport().palette()
        vpal.setColor(QPalette.ColorRole.Window, QColor(t.chrome))
        self._scroll.viewport().setPalette(vpal)
        self.setStyleSheet(
            f"#ddHeader {{ background: {t.chrome};"
            f" border-bottom: 1px solid {t.border}; }}"
            f"#ddTitle {{ color: {t.text}; font-size: 13px; font-weight: 600; }}"
            f"#ddAction {{ background: transparent; border: 0; border-radius: 5px;"
            f" color: {t.accent}; font-size: 12px; padding: 3px 8px; }}"
            f"#ddAction:hover {{ background: {t.hover}; }}"
            f"#ddScroll {{ background: {t.chrome}; border: 0; }}"
        )
