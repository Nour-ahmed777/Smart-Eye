from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from frontend.styles._colors import (
    _ACCENT_BG_12,
    _ACCENT_BG_15,
    _ACCENT_HI_BG_45,
    _ACCENT_HI_BG_70,
    _ACCENT_HI_BG_78,
    _BG_OVERLAY,
    _BG_RAISED,
    _BG_SURFACE_55,
    _BORDER,
)
from frontend.ui_tokens import (
    RADIUS_MD,
    SIZE_CONTROL_MID,
    SIZE_PANEL_SM,
    SIZE_ROW_XL,
    SPACE_6,
    SPACE_10,
    SPACE_MD,
    SPACE_XXXS,
)


def apply_roster_card_style(card: QFrame, object_name: str, is_active: bool) -> None:
    border_color = _ACCENT_HI_BG_70 if is_active else _BORDER
    bg_color = _ACCENT_BG_12 if is_active else _BG_OVERLAY
    hover_border = _ACCENT_HI_BG_78 if is_active else _ACCENT_HI_BG_45
    hover_bg = _ACCENT_BG_15 if is_active else _BG_RAISED
    card.setObjectName(object_name)
    card.setFixedHeight(SIZE_ROW_XL)
    card.setStyleSheet("""
        QFrame#{object_name} {{
            background-color: {bg_color};
            border: {SPACE_XXXS}px solid {border_color};
            border-radius: {RADIUS_MD}px;
        }}
        QFrame#{object_name}:hover {{
            border-color: {hover_border};
            background-color: {hover_bg};
        }}
    """.format(
        object_name=object_name,
        bg_color=bg_color,
        border_color=border_color,
        hover_border=hover_border,
        hover_bg=hover_bg,
        SPACE_XXXS=SPACE_XXXS,
        RADIUS_MD=RADIUS_MD,
    ))


def build_roster_card_layout(card: QFrame) -> tuple[QVBoxLayout, QVBoxLayout, QHBoxLayout, QHBoxLayout]:
    root = QHBoxLayout(card)
    root.setContentsMargins(0, 0, SPACE_10, 0)
    root.setSpacing(0)

    left_cell = QFrame()
    left_cell.setObjectName("RosterLeft")
    left_cell.setFixedWidth(SIZE_PANEL_SM)
    left_cell.setFixedHeight(SIZE_ROW_XL)
    left_cell.setStyleSheet(
        "background: {bg};border-top-left-radius: {radius}px;border-bottom-left-radius: {radius}px;".format(
            bg=_BG_SURFACE_55,
            radius=RADIUS_MD,
        )
    )
    left_layout = QVBoxLayout(left_cell)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(0)
    left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    root.addWidget(left_cell)

    sep_l = QFrame()
    sep_l.setFrameShape(QFrame.Shape.VLine)
    sep_l.setFixedWidth(SPACE_XXXS)
    sep_l.setFixedHeight(SIZE_ROW_XL)
    sep_l.setStyleSheet("background-color: {}; border: none;".format(_BORDER))
    root.addWidget(sep_l)

    body = QHBoxLayout()
    body.setContentsMargins(SPACE_MD, SPACE_10, 0, SPACE_10)
    body.setSpacing(SPACE_10)
    body.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    info_col = QVBoxLayout()
    info_col.setContentsMargins(0, 0, 0, 0)
    body.addLayout(info_col, stretch=1)

    pills_row = QHBoxLayout()
    pills_row.setContentsMargins(0, 0, 0, 0)
    pills_row.setSpacing(SPACE_6)
    body.addLayout(pills_row)

    right_row = QHBoxLayout()
    right_row.setContentsMargins(0, 0, 0, 0)
    right_row.setSpacing(SPACE_6)
    right_wrap = QWidget()
    right_wrap.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    right_wrap.setStyleSheet("background: transparent;")
    right_wrap.setMinimumWidth(SIZE_CONTROL_MID + SPACE_6 * 2)
    right_wrap.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    right_wrap.setLayout(right_row)
    body.addWidget(right_wrap)

    root.addLayout(body)
    return left_layout, info_col, pills_row, right_row
