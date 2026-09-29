"""基于 QWidgetAction 的菜单富行：左图标 + 标题 + 副标题 + 右侧占位（D-3b 放 ×）。

主题色全部来自 Theme；行背景不透明以遮住 QMenu 默认选中色，悬停高亮由
QMenu.hovered 驱动（调用方 set_highlight）。右侧占位区当前留空。
"""
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFontMetrics, QIcon, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

ICON = 20
RIGHT_RESERVED = 22
H_PAD = 12
ICON_GAP = 10


class MenuRow(QWidget):
    def __init__(
        self,
        theme,
        title: str,
        subtitle: str = "",
        icon: QPixmap | QIcon | None = None,
        width: int = 360,
        dim: bool = False,
    ):
        super().__init__()
        self.setObjectName("menuRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedWidth(width)

        self._bg = theme.chrome
        self._hover = theme.hover
        self._title_color = theme.subtext if dim else theme.text
        self._sub_color = theme.subtext

        lay = QHBoxLayout(self)
        lay.setContentsMargins(H_PAD, 6, H_PAD, 6)
        lay.setSpacing(ICON_GAP)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(QSize(ICON, ICON))
        lay.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self._set_icon(icon)

        text_w = width - 2 * H_PAD - ICON - ICON_GAP - RIGHT_RESERVED - ICON_GAP
        if text_w < 60:
            text_w = 60

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)

        fm = QFontMetrics(self.font())
        self._title = QLabel(self)
        self._title.setObjectName("menuRowTitle")
        self._title.setFixedWidth(text_w)
        self._title.setText(fm.elidedText(title or "", Qt.TextElideMode.ElideRight, text_w))
        self._title.setToolTip(title or "")
        col.addWidget(self._title)

        self._sub = QLabel(self)
        self._sub.setObjectName("menuRowSub")
        self._sub.setFixedWidth(text_w)
        self._sub.setText(fm.elidedText(subtitle or "", Qt.TextElideMode.ElideRight, text_w))
        self._sub.setToolTip(subtitle or "")
        self._sub.setVisible(bool(subtitle))
        col.addWidget(self._sub)

        lay.addLayout(col, 1)

        self._right = QWidget(self)
        self._right.setFixedWidth(RIGHT_RESERVED)
        lay.addWidget(self._right)

        self._apply_bg(self._bg)

    def _set_icon(self, icon) -> None:
        if icon is None:
            return
        dpr = self.devicePixelRatioF() or 1.0
        px = int(round(ICON * dpr))
        if isinstance(icon, QPixmap):
            pixmap = icon.scaled(
                px,
                px,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:  # QIcon
            pixmap = icon.pixmap(QSize(px, px))
        if pixmap.isNull():
            return
        pixmap.setDevicePixelRatio(dpr)
        self._icon_label.setPixmap(pixmap)

    def set_highlight(self, on: bool) -> None:
        self._apply_bg(self._hover if on else self._bg)

    def _apply_bg(self, bg: str) -> None:
        self.setStyleSheet(
            f"#menuRow {{ background: {bg}; }}"
            f"#menuRowTitle {{ color: {self._title_color}; font-size: 13px; }}"
            f"#menuRowSub {{ color: {self._sub_color}; font-size: 11px; }}"
        )
