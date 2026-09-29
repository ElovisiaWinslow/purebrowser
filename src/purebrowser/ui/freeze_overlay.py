"""拖动 resize 期间显示的冻结帧：把上一次快照拉伸填满，掩盖 WebEngine 的异步重绘。"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QWidget


class FreezeOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._pixmap: QPixmap | None = None
        self.hide()

    def set_frame(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def clear_frame(self) -> None:
        self._pixmap = None

    def paintEvent(self, event) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        painter = QPainter(self)
        # 拉伸填满整个 overlay（不平铺、不裁剪）
        painter.drawPixmap(self.rect(), self._pixmap)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()  # 尺寸变化后按新尺寸重新拉伸绘制
