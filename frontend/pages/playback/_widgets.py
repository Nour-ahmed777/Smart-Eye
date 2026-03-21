from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel

from frontend.pages.rules_manager._constants import _pill as _rule_pill, _DEL_DEFAULT_SS, _DEL_CONFIRM_SS
from frontend.styles._colors import (
    _ACCENT_BG_12,
    _ACCENT_HI,
    _BG_SURFACE_55,
    _SUCCESS_BG_14,
    _TEXT_PRI,
    _TEXT_MUTED,
)
from frontend.ui_tokens import (
    FONT_SIZE_CAPTION,
    FONT_WEIGHT_BOLD,
    RADIUS_MD,
    SIZE_CONTROL_MID,
    SIZE_CONTROL_MD,
    SIZE_ROW_XL,
    SPACE_XXXS,
)
from frontend.widgets.base.roster_card_base import apply_roster_card_style, build_roster_card_layout
from frontend.widgets.confirm_delete_button import ConfirmDeleteButton


class ClipRowWidget(QFrame):
    clicked = Signal()

    def __init__(self, name: str, tag: str, ts: float, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._active = False
        self.setFixedHeight(SIZE_ROW_XL)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(name, tag, ts)

    def _build(self, name: str, tag: str, ts: float) -> None:
        apply_roster_card_style(self, "ClipCard", is_active=self._active)
        left_layout, info_col, pills_row, right_row = build_roster_card_layout(self)

        left_cell = self.findChild(QFrame, "RosterLeft")
        if left_cell:
            left_cell.setStyleSheet(
                f"background: {_BG_SURFACE_55}; margin: {SPACE_XXXS}px;"
                f"border-top-left-radius: {RADIUS_MD}px; border-bottom-left-radius: {RADIUS_MD}px;"
            )

        left_cell = self.findChild(QFrame, "RosterLeft")
        if left_cell:
            left_cell.setVisible(False)
        for child in self.findChildren(QFrame):
            if child.frameShape() == QFrame.Shape.VLine:
                child.setVisible(False)

        title = QLabel(name)
        title.setStyleSheet(f"color: {_TEXT_PRI}; font-size: {FONT_SIZE_CAPTION}px; font-weight: {FONT_WEIGHT_BOLD};")
        info_col.addWidget(title)

        ts_text = datetime.fromtimestamp(ts).strftime("%b %d, %Y  %H:%M")
        subtitle = QLabel(ts_text)
        subtitle.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px;")
        info_col.addWidget(subtitle)

        # No tag pill for clips

        self._delete_btn = ConfirmDeleteButton("Delete", "Sure?")
        self._delete_btn.set_button_styles(_DEL_DEFAULT_SS, _DEL_CONFIRM_SS)
        right_row.addWidget(self._delete_btn)

    def set_active(self, active: bool) -> None:
        self._active = active
        apply_roster_card_style(self, "ClipCard", is_active=active)

    def set_delete_callback(self, fn) -> None:
        self._delete_btn.set_confirm_callback(fn)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
