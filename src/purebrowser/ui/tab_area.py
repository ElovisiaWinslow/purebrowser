"""TabArea：QTabBar + QStackedWidget 的薄封装，提供 QTabWidget 兼容 API。

用于把标签栏从 QTabWidget 中解耦，方便后续与窗口控制按钮同行布局（B-2.2）。
"""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from purebrowser.ui.tabbar import AdaptiveTabBar


class TabArea(QWidget):
    currentChanged = pyqtSignal(int)
    tabCloseRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._syncing = False
        self._bar = AdaptiveTabBar(self)
        self._stack = QStackedWidget(self)
        self._stack.setStyleSheet("QStackedWidget { border: 0; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._bar)
        lay.addWidget(self._stack, 1)

        self._bar.currentChanged.connect(self._on_bar_current_changed)
        self._bar.tabMoved.connect(self._on_tab_moved)
        self._bar.tabCloseRequested.connect(self.tabCloseRequested)

    # ---------- 标签栏访问 ----------
    def tabBar(self) -> AdaptiveTabBar:
        return self._bar

    # ---------- QTabWidget 兼容 API ----------
    def setTabBar(self, bar) -> None:
        # 使用内建 _bar；外部传入的丢弃，避免游离控件。
        if bar is not self._bar:
            bar.setParent(None)
            bar.deleteLater()

    def setTabsClosable(self, flag) -> None:
        # 使用自建关闭键（_install_tab_close），内建关闭键不用。
        pass

    def setMovable(self, flag) -> None:
        self._bar.setMovable(flag)

    def setDocumentMode(self, flag) -> None:
        self._bar.setDrawBase(not flag)

    def setUsesScrollButtons(self, flag) -> None:
        self._bar.setUsesScrollButtons(flag)

    def setTabText(self, index, text) -> None:
        self._bar.setTabText(index, text)

    def addTab(self, widget, label):
        self._syncing = True
        try:
            idx = self._stack.addWidget(widget)
            self._bar.addTab(label)
        finally:
            self._syncing = False
        # bar.addTab 在空表时会自动把 0 设为当前，这里对齐 stack。
        self._stack.setCurrentIndex(max(0, self._bar.currentIndex()))
        return idx

    def removeTab(self, index) -> None:
        self._syncing = True
        try:
            w = self._stack.widget(index)
            if w is not None:
                self._stack.removeWidget(w)
            self._bar.removeTab(index)
        finally:
            self._syncing = False
        ci = self._bar.currentIndex()
        if 0 <= ci < self._stack.count():
            self._stack.setCurrentIndex(ci)

    def indexOf(self, widget) -> int:
        return self._stack.indexOf(widget)

    def count(self) -> int:
        return self._stack.count()

    def widget(self, index):
        return self._stack.widget(index)

    def currentWidget(self):
        return self._stack.currentWidget()

    def currentIndex(self) -> int:
        return self._bar.currentIndex()

    def setCurrentIndex(self, index) -> None:
        self._bar.setCurrentIndex(index)
        self._stack.setCurrentIndex(index)

    # ---------- 内部信号 ----------
    def _on_bar_current_changed(self, index) -> None:
        if self._syncing:
            return
        self._stack.setCurrentIndex(index)
        self.currentChanged.emit(index)

    def _on_tab_moved(self, from_: int, to: int) -> None:
        w = self._stack.widget(from_)
        if w is None:
            return
        self._syncing = True
        try:
            self._stack.removeWidget(w)
            self._stack.insertWidget(to, w)
        finally:
            self._syncing = False
        self._stack.setCurrentIndex(max(0, self._bar.currentIndex()))
