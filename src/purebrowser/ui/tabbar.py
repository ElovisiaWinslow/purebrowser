"""自适应等宽标签栏：所有标签等宽，宽度在 [HARD_W, MAX_W] 之间。"""
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QTabBar


class AdaptiveTabBar(QTabBar):
    HARD_W = 8        # 真正的最小宽度，只防 w = 0
    MAX_W = 220
    TAB_H = 38
    RESERVED = 40     # 给 + 按钮预留（宽 28 + 间隙 12）

    def tabSizeHint(self, index: int) -> QSize:
        count = self.count()
        if count == 0:
            return QSize(self.MAX_W, self.TAB_H)
        avail = self.width() - self.RESERVED
        if avail < 1:
            avail = 1
        w = avail // count
        if w > self.MAX_W:
            w = self.MAX_W
        if w < self.HARD_W:
            w = self.HARD_W
        return QSize(w, self.TAB_H)

    def minimumTabSizeHint(self, index: int) -> QSize:
        return QSize(self.HARD_W, self.TAB_H)

    def minimumSizeHint(self) -> QSize:
        # 控制标签栏自身的最小宽度：不随标签数增长，否则溢出时会把 TopRightCorner / + 顶出窗口。
        return QSize(self.HARD_W, self.TAB_H)
