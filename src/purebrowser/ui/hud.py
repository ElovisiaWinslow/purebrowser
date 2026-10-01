"""共享浮层组件：浮在内容区之上、可交互、按锚点定位、支持短暂显示。

ZoomHud 目前的使用者；后续查找条可复用 FloatingHud（commit B）。

设计要点：
- 默认**不**设置 WA_TransparentForMouseEvents，浮层可点击；
  需要穿透时调用 set_click_through(True)。
- 挂到 tabs.stack() 上，父控件 resize 时自动重新定位。
- show_briefly(ms) 显示后定时隐藏；鼠标悬停时暂停，离开后重新计时。
"""
from PyQt6.QtCore import QElapsedTimer, QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)


def _capsule_qss(root: str) -> str:
    """深色半透明胶囊样式：ZoomHud / FindHud 共用，保证外观一致。"""
    return f"""
#{root} {{
    background: rgba(24, 24, 26, 0.90);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
}}
#{root} QToolButton {{
    color: #FFFFFF;
    background: transparent;
    border: 0;
    border-radius: 6px;
    min-width: 28px;
    min-height: 28px;
    padding: 0;
    font-size: 15px;
    font-weight: 600;
}}
#{root} QToolButton:hover {{ background: rgba(255, 255, 255, 0.18); }}
#{root} QToolButton:pressed {{ background: rgba(255, 255, 255, 0.30); }}
#{root} QLabel {{ color: #FFFFFF; font-size: 12px; }}
#{root} QLineEdit {{
    color: #FFFFFF;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.36);
    border-radius: 6px;
    font-size: 13px;
    padding: 2px 8px;
    selection-background-color: rgba(255, 255, 255, 0.35);
    selection-color: #FFFFFF;
}}
"""


_ZOOM_QSS = _capsule_qss("zoomHud") + """
#zoomHud #hudPercent {
    font-size: 13px;
    min-width: 48px;
    padding: 0 4px;
}
#zoomHud #hudEditor {
    min-width: 48px;
    max-width: 56px;
    padding: 2px 4px;
}
"""

_FIND_QSS = _capsule_qss("findHud") + """
#findHud #findInput {
    min-width: 200px;
    max-width: 280px;
}
#findHud #findCount {
    min-width: 44px;
}
"""


class FloatingHud(QWidget):
    def __init__(self, parent: QWidget, anchor: str = "bottom-right", margin: int = 16,
                 bottom_offset: int = 0):
        super().__init__(parent)
        self._anchor = anchor
        self._margin = int(margin)
        self._bottom_offset = int(bottom_offset)
        self._hovered = False
        self._autohide_enabled = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()

        self._autohide = QTimer(self)
        self._autohide.setSingleShot(True)
        self._autohide.timeout.connect(self._on_autohide)

        if parent is not None:
            parent.installEventFilter(self)

    def set_click_through(self, enabled: bool) -> None:
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, bool(enabled)
        )

    def show_briefly(self, ms: int = 2000) -> None:
        self._autohide_enabled = True
        self._reposition()
        self.show()
        self.raise_()
        self._autohide.start(ms)

    def show_persistent(self) -> None:
        """常驻显示，不自动隐藏（鼠标移出也不会触发隐藏）。"""
        self._autohide_enabled = False
        self._autohide.stop()
        self._reposition()
        self.show()
        self.raise_()

    def _on_autohide(self) -> None:
        if self._hovered:
            return
        self.hide()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        hint = self.sizeHint()
        self.resize(hint)
        pw, ph = parent.width(), parent.height()
        w, h = hint.width(), hint.height()
        m = self._margin
        off = self._bottom_offset
        if self._anchor == "top-right":
            x, y = pw - w - m, m
        elif self._anchor == "top-left":
            x, y = m, m
        elif self._anchor == "bottom-left":
            x, y = m, ph - h - m - off
        else:  # bottom-right
            x, y = pw - w - m, ph - h - m - off
        self.move(max(0, x), max(0, y))
        self.raise_()

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            if self.isVisible():
                self._reposition()
        return super().eventFilter(obj, event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._autohide.stop()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        if self.isVisible() and self._autohide_enabled:
            self._autohide.start(2000)
        super().leaveEvent(event)


class ZoomHud(FloatingHud):
    step_requested = pyqtSignal(int)
    percent_requested = pyqtSignal(int)
    reset_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, anchor="bottom-right", margin=16)
        self.setObjectName("zoomHud")
        self.setStyleSheet(_ZOOM_QSS)
        self._percent = 100

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)

        self._minus = QToolButton(self)
        self._minus.setText("\u2212")
        self._minus.setToolTip("缩小")
        self._minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._minus.clicked.connect(lambda: self.step_requested.emit(-1))
        lay.addWidget(self._minus)

        self._percent_btn = QToolButton(self)
        self._percent_btn.setObjectName("hudPercent")
        self._percent_btn.setText("100%")
        self._percent_btn.setToolTip("点击输入缩放百分比（25–500）")
        self._percent_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._percent_btn.clicked.connect(self._begin_edit)
        lay.addWidget(self._percent_btn)

        self._editor = QLineEdit(self)
        self._editor.setObjectName("hudEditor")
        self._editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._editor.setVisible(False)
        self._editor.returnPressed.connect(self._commit_edit)
        self._editor.editingFinished.connect(self._commit_edit)
        lay.addWidget(self._editor)

        self._plus = QToolButton(self)
        self._plus.setText("+")
        self._plus.setToolTip("放大")
        self._plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._plus.clicked.connect(lambda: self.step_requested.emit(1))
        lay.addWidget(self._plus)

        self._reset = QToolButton(self)
        self._reset.setText("\u27F2")
        self._reset.setToolTip("重置为 100%")
        self._reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset.clicked.connect(lambda: self.reset_requested.emit())
        lay.addWidget(self._reset)

    def show_percent(self, factor: float, ms: int = 2000) -> None:
        self._end_edit()
        self._percent = int(round(factor * 100))
        self._percent_btn.setText(f"{self._percent}%")
        self.show_briefly(ms)

    def _begin_edit(self) -> None:
        self._editor.setText(str(self._percent))
        self._percent_btn.setVisible(False)
        self._editor.setVisible(True)
        self._editor.setFocus()
        self._editor.selectAll()
        self._autohide.stop()

    def _commit_edit(self) -> None:
        if not self._editor.isVisible():
            return
        text = self._editor.text().strip()
        self._end_edit()
        try:
            value = int(text)
        except ValueError:
            return
        value = max(25, min(500, value))
        self.percent_requested.emit(value)

    def _end_edit(self) -> None:
        self._editor.setVisible(False)
        self._percent_btn.setVisible(True)


class FindHud(FloatingHud):
    """页面内查找浮层（Ctrl+F），右上角常驻，复用胶囊外观。"""

    text_changed = pyqtSignal(str)
    next_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, anchor="top-right", margin=16)
        self.setObjectName("findHud")
        self.setStyleSheet(_FIND_QSS)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)

        self.input = QLineEdit(self)
        self.input.setObjectName("findInput")
        self.input.setPlaceholderText("在页面中查找")
        self.input.textChanged.connect(self.text_changed)
        self.input.returnPressed.connect(self.next_requested)
        lay.addWidget(self.input)

        self.count = QLabel("0/0", self)
        self.count.setObjectName("findCount")
        self.count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.count)

        self.prev_btn = QToolButton(self)
        self.prev_btn.setText("\u2191")
        self.prev_btn.setToolTip("上一个")
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.clicked.connect(lambda: self.prev_requested.emit())
        lay.addWidget(self.prev_btn)

        self.next_btn = QToolButton(self)
        self.next_btn.setText("\u2193")
        self.next_btn.setToolTip("下一个")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(lambda: self.next_requested.emit())
        lay.addWidget(self.next_btn)

        self.close_btn = QToolButton(self)
        self.close_btn.setText("\u00D7")
        self.close_btn.setToolTip("关闭")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(lambda: self.close_requested.emit())
        lay.addWidget(self.close_btn)

    def open(self) -> None:
        self.show_persistent()
        self.input.setFocus()
        self.input.selectAll()

    def set_count(self, text: str) -> None:
        self.count.setText(text)


class WheelZoomFilter(QObject):
    """把 Ctrl+滚轮桥接到 on_step(direction)，并阻止 QtWebEngine 原生缩放。

    非 Ctrl 滚轮返回 False，普通滚动不受影响。
    """

    STEP_UNITS = 120
    THROTTLE_MS = 40

    def __init__(self, on_step):
        super().__init__()
        self._on_step = on_step
        self._acc = 0
        self._last = QElapsedTimer()
        self._last.start()

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.Wheel:
            return False
        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            return False
        dy = event.angleDelta().y() or event.pixelDelta().y()
        if event.inverted():
            dy = -dy
        if dy == 0:
            return True
        self._acc += dy
        if abs(self._acc) >= self.STEP_UNITS and self._last.elapsed() >= self.THROTTLE_MS:
            direction = 1 if self._acc > 0 else -1
            self._acc = 0
            self._last.restart()
            self._on_step(direction)
        return True
