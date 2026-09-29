"""自适应等宽标签栏：所有标签等宽，宽度在 [MIN_W, MAX_W] 之间。"""
from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QTabBar


class AdaptiveTabBar(QTabBar):
    MIN_W = 32
    MAX_W = 220
    TAB_H = 38

    def tabSizeHint(self, index: int) -> QSize:
        count = self.count()
        if count == 0:
            return QSize(self.MAX_W, self.TAB_H)
        avail = self.width()
        if avail <= 0:
            return QSize(self.MAX_W, self.TAB_H)
        w = avail // count
        if w > self.MAX_W:
            w = self.MAX_W
        if w < self.MIN_W:
            w = self.MIN_W
        return QSize(w, self.TAB_H)

    def minimumTabSizeHint(self, index: int) -> QSize:
        return QSize(self.MIN_W, self.TAB_H)

    def minimumSizeHint(self) -> QSize:
        # 控制标签栏自身的最小宽度：若让它随标签数增长（count*MIN_W），
        # 溢出时整条标签栏会被撑宽，TopRightCorner 的 + 会被顶到窗口外。
        # 固定为单个 MIN_W，标签栏保持可用宽度，溢出的标签被裁剪，+ 始终可见。
        return QSize(self.MIN_W, self.TAB_H)
