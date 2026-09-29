"""共享浮层组件：浮在内容区之上、可交互、按锚点定位、支持短暂显示。

ZoomHud 目前的使用者；后续查找条可复用 FloatingHud（commit B）。

设计要点：
- 默认**不**设置 WA_TransparentForMouseEvents，浮层可点击；
  需要穿透时调用 set_click_through(True)。
- 挂到 tabs.stack() 上，父控件 resize 时自动重新定位。
- show_briefly(ms) 显示后定时隐藏；鼠标悬停时暂停，离开后重新计时。
"""
from PyQt6.QtCore import QElapsedTimer, QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QToolButton, QWidget

_ZOOM_QSS = """
#zoomHud {
    background: rgba(24, 24, 26, 0.90);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
}
#zoomHud QToolButton {
    color: #FFFFFF;
    background: transparent;
    border: 0;
    border-radius: 6px;
    min-width: 28px;
    min-height: 28px;
    padding: 0;
    font-size: 15px;
    font-weight: 600;
}
#zoomHud QToolButton:hover { background: rgba(255, 255, 255, 0.18); }
#zoomHud QToolButton:pressed { background: rgba(255, 255, 255, 0.30); }
#zoomHud #hudPercent {
    font-size: 13px;
    min-width: 48px;
    padding: 0 4px;
}
#zoomHud #hudEditor {
    color: #FFFFFF;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.40);
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    min-width: 48px;
    max-width: 56px;
    padding: 2px 4px;
}
"""


class FloatingHud(QWidget):
    def __init__(self, parent: QWidget, anchor: str = "bottom-right", margin: int = 16):
        super().__init__(parent)
        self._anchor = anchor
        self._margin = int(margin)
        self._hovered = False
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
        self._reposition()
        self.show()
        self.raise_()
        self._autohide.start(ms)

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
        if self._anchor == "top-right":
            x, y = pw - w - m, m
        elif self._anchor == "top-left":
            x, y = m, m
        elif self._anchor == "bottom-left":
            x, y = m, ph - h - m
        else:  # bottom-right
            x, y = pw - w - m, ph - h - m
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
        if self.isVisible():
            self._autohide.start(2000)
        super().leaveEvent(event)


class ZoomHud(FloatingHud):
    step_requested = pyqtSignal(int)
    percent_requested = pyqtSignal(int)

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
