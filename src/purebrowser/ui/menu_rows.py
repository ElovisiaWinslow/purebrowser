"""菜单/下拉通用富行：左图标 + 标题 + 副标题（+ 可选细进度条）+ 右侧按钮组。

- 右侧按钮组由 `buttons` 描述（列表，每项 {id, icon?, text?, tooltip?}）；
  旧的 `deletable=True` 等价于单按钮组（内容 "×"，id="delete"）。
- 悬停由 enter/leave 驱动：悬停高亮 + 显示右侧按钮（行宽始终预留按钮位，避免抖动）。
- body 被点击：clicked(row, new_tab)（new_tab = 中键或 Ctrl+左键）。
- 右侧按钮点击独立于整行；通过 action_requested(row, button_id) 上报。
- set_subtitle/set_progress 支持下载进度实时原地刷新。
"""
from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QFontMetrics, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

ICON = 20
RIGHT_RESERVED = 22
H_PAD = 12
ICON_GAP = 10
BTN = 20
BTN_GAP = 2


class MenuRow(QWidget):
    action_requested = pyqtSignal(object, str)
    clicked = pyqtSignal(object, bool)

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
        progress: int | None = None,
    ):
        super().__init__()
        self.setObjectName("menuRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedWidth(width)

        self._bg = theme.chrome
        self._hover = theme.hover
        self._border = theme.border
        self._accent = theme.accent
        self._title_color = theme.subtext if dim else theme.text
        self._sub_color = theme.subtext
        self._strong_text = theme.text
        self._hovered = False

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
        self._text_w = text_w

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

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
        self._full_subtitle = subtitle or ""
        self._sub.setText(fm.elidedText(self._full_subtitle, Qt.TextElideMode.ElideRight, text_w))
        self._sub.setToolTip(self._full_subtitle)
        self._sub.setVisible(bool(self._full_subtitle))
        col.addWidget(self._sub)

        self._bar = None
        if progress is not None:
            self._bar = QProgressBar(self)
            self._bar.setObjectName("menuRowBar")
            self._bar.setRange(0, 100)
            self._bar.setValue(max(0, min(100, int(progress))))
            self._bar.setTextVisible(False)
            self._bar.setFixedWidth(text_w)
            self._bar.setFixedHeight(4)
            col.addWidget(self._bar)

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

        self._apply_style()
        self._install_hover_tracking()

    def _install_hover_tracking(self) -> None:
        """监听自身与所有子控件的 Enter/Leave，按光标是否仍在整行内决定高亮。

        只靠自身 enter/leave 会漏事件（鼠标移到子控件上、快速移出、面板隐藏），
        导致"选中效果赖着不消失"。这里统一在收尾时用 QCursor 位置对账。
        """
        self.installEventFilter(self)
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        et = event.type()
        if et in (
            QEvent.Type.Enter,
            QEvent.Type.Leave,
            QEvent.Type.HoverEnter,
            QEvent.Type.HoverLeave,
        ):
            self._sync_hover()
        return super().eventFilter(obj, event)

    def hideEvent(self, event) -> None:
        self._set_hovered(False)
        super().hideEvent(event)

    def _sync_hover(self) -> None:
        inside = False
        if self.isVisible():
            try:
                inside = self.rect().contains(self.mapFromGlobal(QCursor.pos()))
            except Exception:
                inside = False
        self._set_hovered(inside)

    # ---------- live updates ----------
    def set_subtitle(self, text: str) -> None:
        text = text or ""
        self._full_subtitle = text
        fm = QFontMetrics(self.font())
        self._sub.setText(fm.elidedText(text, Qt.TextElideMode.ElideRight, self._text_w))
        self._sub.setToolTip(text)
        self._sub.setVisible(bool(text))

    def set_progress(self, value: int) -> None:
        if self._bar is not None:
            self._bar.setValue(max(0, min(100, int(value))))

    # ---------- events ----------
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.clicked.emit(self, True)
        elif event.button() == Qt.MouseButton.LeftButton:
            new_tab = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            self.clicked.emit(self, new_tab)

    # ---------- internal ----------
    def _emit_action(self, button_id: str) -> None:
        self.action_requested.emit(self, button_id)

    def _set_hovered(self, on: bool) -> None:
        if self._hovered == on:
            return
        self._hovered = on
        self._apply_style()
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

    def _apply_style(self) -> None:
        bg = self._hover if self._hovered else self._bg
        self.setStyleSheet(
            f"#menuRow {{ background: {bg}; }}"
            f"#menuRowTitle {{ color: {self._title_color}; font-size: 13px; }}"
            f"#menuRowSub {{ color: {self._sub_color}; font-size: 11px; }}"
            f"#menuRowBar {{ background: {self._border}; border: 0; border-radius: 2px; }}"
            f"#menuRowBar::chunk {{ background: {self._accent}; border-radius: 2px; }}"
            f"#menuRowBtn {{ background: transparent; border: 0; border-radius: 4px;"
            f" font-size: 13px; color: {self._sub_color}; }}"
            f"#menuRowBtn:hover {{ background: {self._border}; }}"
        )
