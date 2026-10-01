"""自绘不透明右键菜单。

不用 QMenu：Qt 的 QMenu 永远是 layered/translucent 窗口，且每次 hover 高亮
重绘约 1.26ms。菜单浮在正在播放的视频上时，鼠标每移动一次都要在 GUI 线程
重绘 + 让 DWM 对视频区域做 alpha 合成，表现为「高亮不跟手 + 视频掉帧」。
这里改用普通 QWidget(Qt.Popup) + QPainter 自绘：非 layered、重绘约 0.11ms。

用法::

    menu = ContextMenu(theme)
    menu.set_entries([
        action("复制", callback),
        separator(),
        action("刷新", callback, enabled=False),
    ])
    menu.popup(global_pos)
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFontMetrics, QPainter
from PyQt6.QtWidgets import QApplication, QWidget

_ITEM_H = 26
_PAD_X = 14
_PAD_Y = 5
_SEP_H = 9
_MIN_W = 90


class _Entry:
    __slots__ = ("text", "enabled", "sep", "callback")

    def __init__(self, text="", enabled=True, sep=False, callback=None):
        self.text = text
        self.enabled = enabled
        self.sep = sep
        self.callback = callback


def action(text: str, callback, enabled: bool = True) -> _Entry:
    return _Entry(text=text, enabled=enabled, callback=callback)


def separator() -> _Entry:
    return _Entry(sep=True)


class ContextMenu(QWidget):
    def __init__(self, theme):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._c_bg = QColor(theme.chrome)
        self._c_border = QColor(theme.border)
        self._c_text = QColor(theme.text)
        self._c_sub = QColor(theme.subtext)
        self._c_hl = QColor(theme.accent)
        self._c_hl_text = QColor(theme.on_accent)
        self._entries: list[_Entry] = []
        self._rects: list[QRect] = []
        self._active = -1
        # 不透明自绘：非 layered，不继承全局 QSS 的圆角/阴影。
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ---------- API ----------
    def set_entries(self, entries) -> None:
        self._entries = list(entries)
        self._active = -1
        self._relayout()

    def popup(self, global_pos: QPoint) -> None:
        self._active = -1
        self._relayout()
        self.move(self._clamp(global_pos))
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    # ---------- layout ----------
    def _relayout(self) -> None:
        fm = QFontMetrics(self.font())
        width = 0
        for e in self._entries:
            if not e.sep:
                width = max(width, fm.horizontalAdvance(e.text))
        width = max(_MIN_W, width + 2 * _PAD_X)
        y = _PAD_Y
        self._rects = []
        for e in self._entries:
            h = _SEP_H if e.sep else _ITEM_H
            self._rects.append(QRect(0, y, width, h))
            y += h
        self.resize(width, y + _PAD_Y)

    def sizeHint(self) -> QSize:
        return QSize(self.width(), self.height())

    def _clamp(self, pos: QPoint) -> QPoint:
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        if screen is None:
            return pos
        g = screen.availableGeometry()
        x = min(max(pos.x(), g.left()), max(g.left(), g.right() - self.width() + 1))
        y = min(max(pos.y(), g.top()), max(g.top(), g.bottom() - self.height() + 1))
        return QPoint(x, y)

    def _index_at(self, pos: QPoint) -> int:
        for i, r in enumerate(self._rects):
            if r.contains(pos):
                return i
        return -1

    # ---------- events ----------
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), self._c_bg)
        p.setPen(self._c_border)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        fm = QFontMetrics(self.font())
        for i, e in enumerate(self._entries):
            r = self._rects[i]
            if e.sep:
                p.setPen(self._c_border)
                p.drawLine(r.left() + 8, r.center().y(), r.right() - 8, r.center().y())
                continue
            if i == self._active:
                p.fillRect(r.adjusted(1, 0, -1, 0), self._c_hl)
                p.setPen(self._c_hl_text)
            else:
                p.setPen(self._c_text if e.enabled else self._c_sub)
            text = fm.elidedText(e.text, Qt.TextElideMode.ElideRight, r.width() - 2 * _PAD_X)
            p.drawText(
                r.adjusted(_PAD_X, 0, 0, 0),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                text,
            )

    def mouseMoveEvent(self, event) -> None:
        idx = self._index_at(event.position().toPoint())
        if 0 <= idx < len(self._entries):
            e = self._entries[idx]
            if e.sep or not e.enabled:
                idx = -1
        if idx == self._active:
            return
        old = self._active
        self._active = idx
        if 0 <= old < len(self._rects):
            self.update(self._rects[old])
        if 0 <= idx < len(self._rects):
            self.update(self._rects[idx])

    def leaveEvent(self, event) -> None:
        if self._active >= 0:
            old = self._active
            self._active = -1
            if 0 <= old < len(self._rects):
                self.update(self._rects[old])

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            self.hide()
            return
        idx = self._index_at(event.position().toPoint())
        self.hide()
        if 0 <= idx < len(self._entries):
            e = self._entries[idx]
            if not e.sep and e.enabled and e.callback is not None:
                e.callback()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
