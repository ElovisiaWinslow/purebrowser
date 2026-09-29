"""自适应等宽标签栏：所有标签等宽，宽度在 [MIN_W, MAX_W] 之间。

右边界（content_right = width - RESERVED）由本控件强制保证：
- tabSizeHint 只使用 content_right；
- paintEvent 用 widget mask 把绘制裁剪到 content_right（QTabBar 自建 QPainter，
  无法注入 clipRect，widget mask 效果等价）。
"""
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QRegion
from PyQt6.QtWidgets import QTabBar


class AdaptiveTabBar(QTabBar):
    MIN_W = 32
    MAX_W = 220
    TAB_H = 38
    RESERVED = 40  # 给 + 按钮预留（宽 28 + 间隙 12）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._relayout_cb = None

    def set_relayout_callback(self, cb) -> None:
        self._relayout_cb = cb

    def content_right(self) -> int:
        """标签允许绘制/布局的右边界（+ 按钮在此之外）。"""
        return max(0, self.width() - self.RESERVED)

    def tabSizeHint(self, index: int) -> QSize:
        count = self.count()
        if count == 0:
            return QSize(self.MAX_W, self.TAB_H)
        avail = self.content_right()
        if avail < 1:
            avail = 1
        w = avail // count
        if w > self.MAX_W:
            w = self.MAX_W
        if w < self.MIN_W:
            w = self.MIN_W
        return QSize(w, self.TAB_H)

    def minimumTabSizeHint(self, index: int) -> QSize:
        return QSize(self.MIN_W, self.TAB_H)

    def minimumSizeHint(self) -> QSize:
        # 不随标签数增长，避免溢出时把 + 顶出窗口。
        return QSize(self.MIN_W, self.TAB_H)

    def _clip_to_content(self) -> None:
        w = self.content_right()
        h = self.height()
        if w <= 0 or h <= 0:
            if self.mask():
                self.clearMask()
            return
        region = QRegion(0, 0, w, h)
        if self.mask() != region:
            self.setMask(region)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._clip_to_content()
        if self._relayout_cb is not None:
            self._relayout_cb()

    def paintEvent(self, event) -> None:
        # 保证绘制不越过 content_right（几何上也不应，但这里是最后一道保险）。
        self._clip_to_content()
        super().paintEvent(event)
