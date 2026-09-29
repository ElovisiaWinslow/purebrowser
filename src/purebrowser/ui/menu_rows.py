"""基于 QWidgetAction 的菜单富行：左图标 + 标题 + 副标题 + 右侧按钮组。

- 右侧按钮组由 `buttons` 描述（列表，每项 {id, icon?, text?, tooltip?}）；
  旧的 `deletable=True` 等价于单按钮组（内容 "×"，id="delete"）。
- 主题色全部来自 Theme；行背景不透明以遮住 QMenu 默认选中色，悬停高亮由
  QMenu.hovered 驱动（调用方 set_highlight），按钮随 hover 显示/隐藏。
- 按钮点击独立于整行（不透传）；通过 action_requested(row, button_id) 上报。
"""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QIcon, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

ICON = 20
RIGHT_RESERVED = 22
H_PAD = 12
ICON_GAP = 10
BTN = 20
BTN_GAP = 2


class MenuRow(QWidget):
    delete_requested = pyqtSignal(object)
    action_requested = pyqtSignal(object, str)

    def __init__(
        self,
        theme,
        title: str,
        subtitle: str = "",
        icon: QPixmap | QIcon | None = None,
        width: int = 360,
        dim: bool = False,
        deletable: bool = False,
        buttons: list | None = None,
    ):
        super().__init__()
        self.setObjectName("menuRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedWidth(width)

        self._bg = theme.chrome
        self._hover = theme.hover
        self._border = theme.border
        self._title_color = theme.subtext if dim else theme.text
        self._sub_color = theme.subtext
        self._strong_text = theme.text

        specs = list(buttons) if buttons else []
        if not specs and deletable:
            specs = [{"id": "delete", "text": "\u00D7", "tooltip": "删除"}]
        n = len(specs)
        right_w = (n * BTN + (n - 1) * BTN_GAP) if n else RIGHT_RESERVED

        lay = QHBoxLayout(self)
        lay.setContentsMargins(H_PAD, 6, H_PAD, 6)
        lay.setSpacing(ICON_GAP)

        self._icon_label = QLabel(self)
        self._icon_label.setFixedSize(QSize(ICON, ICON))
        lay.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self._set_icon(icon)

        text_w = width - 2 * H_PAD - ICON - ICON_GAP - right_w
        if n:
            text_w -= ICON_GAP
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

        self._buttons: list[QToolButton] = []
        self._button_ids: list[str] = []
        if n:
            box = QHBoxLayout()
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(BTN_GAP)
            for spec in specs:
                btn = QToolButton(self)
                btn.setObjectName("menuRowBtn")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedSize(BTN, BTN)
                btn.setVisible(False)
                if spec.get("icon") is not None:
                    btn.setIcon(spec["icon"])
                    btn.setIconSize(QSize(BTN - 4, BTN - 4))
                if spec.get("text"):
                    btn.setText(spec["text"])
                btn.setToolTip(spec.get("tooltip", ""))
                bid = spec["id"]
                btn.clicked.connect(lambda _=False, i=bid: self._emit_action(i))
                box.addWidget(btn)
                self._buttons.append(btn)
                self._button_ids.append(bid)
            lay.addLayout(box)

        self._apply_bg(self._bg)

    def _emit_action(self, button_id: str) -> None:
        self.action_requested.emit(self, button_id)
        if button_id == "delete":
            self.delete_requested.emit(self)

    def set_highlight(self, on: bool) -> None:
        self._apply_bg(self._hover if on else self._bg)
        for btn in self._buttons:
            btn.setVisible(on)

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

    def _apply_bg(self, bg: str) -> None:
        self.setStyleSheet(
            f"#menuRow {{ background: {bg}; }}"
            f"#menuRowTitle {{ color: {self._title_color}; font-size: 13px; }}"
            f"#menuRowSub {{ color: {self._sub_color}; font-size: 11px; }}"
            f"#menuRowBtn {{ background: transparent; border: 0; border-radius: 4px;"
            f" font-size: 13px; }}"
            f"#menuRowBtn:hover {{ background: {self._border}; }}"
        )
