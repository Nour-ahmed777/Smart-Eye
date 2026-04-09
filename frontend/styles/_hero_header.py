from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from frontend.app_theme import safe_set_point_size
from frontend.icon_theme import themed_icon_pixmap
from frontend.styles._colors import _BG_RAISED, _BORDER, _TEXT_MUTED, _TEXT_PRI, _TEXT_SEC
from frontend.ui_tokens import (
    FONT_SIZE_LABEL,
    FONT_SIZE_SUBHEAD,
    RADIUS_LG,
    SIZE_ICON_64,
    SIZE_HERO_HEADER,
    SIZE_ROW_72,
    SPACE_14,
    SPACE_20,
    SPACE_XS,
    SPACE_XXXS,
)


def make_hero_header(
    icon_path: str,
    title: str,
    subtitle: str,
    right_text: str | None = None,
    right_widget=None,
    left_widget=None,
    parent=None,
) -> QFrame:
    hero = QFrame(parent)
    hero.setStyleSheet(f"QFrame{{background:{_BG_RAISED};border:none;}}")
    hero.setFixedHeight(SIZE_HERO_HEADER)
    hl = QHBoxLayout(hero)
    hl.setContentsMargins(SPACE_20, SPACE_14, SPACE_20, SPACE_14)
    hl.setSpacing(SPACE_14)
    hl.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    icon_wrap = None
    if icon_path:
        icon_wrap = QFrame()
        icon_wrap.setFixedSize(SIZE_ROW_72, SIZE_ROW_72)
        icon_wrap.setStyleSheet(f"background:{_BG_RAISED}; border:{SPACE_XXXS}px solid {_BORDER}; border-radius:{RADIUS_LG}px;")
        iw = QVBoxLayout(icon_wrap)
        iw.setContentsMargins(SPACE_XS, SPACE_XS, SPACE_XS, SPACE_XS)
        iw.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(SIZE_ICON_64, SIZE_ICON_64)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = themed_icon_pixmap(icon_path, SIZE_ICON_64, SIZE_ICON_64)
        if not pix.isNull():
            icon_lbl.setPixmap(pix)
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        iw.addWidget(icon_lbl)
    if left_widget is not None:
        hl.addWidget(left_widget)
    elif icon_wrap is not None:
        hl.addWidget(icon_wrap)

    col = QVBoxLayout()
    col.setSpacing(SPACE_XS)
    nf = QFont()
    safe_set_point_size(nf, FONT_SIZE_SUBHEAD)
    nf.setBold(True)
    title_lbl = QLabel(title)
    title_lbl.setFont(nf)
    title_lbl.setStyleSheet(f"color:{_TEXT_PRI};")
    col.addWidget(title_lbl)
    sub_lbl = QLabel(subtitle)
    sub_lbl.setStyleSheet(f"color:{_TEXT_SEC}; font-size:{FONT_SIZE_LABEL}px;")
    sub_lbl.setWordWrap(True)
    col.addWidget(sub_lbl)
    hl.addLayout(col, stretch=1)

    if right_widget is not None:
        hl.addWidget(right_widget)
    elif right_text:
        rt = QLabel(right_text)
        rt.setStyleSheet(f"color:{_TEXT_MUTED}; font-size:{FONT_SIZE_LABEL}px;")
        hl.addWidget(rt)

    return hero
