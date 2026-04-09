from frontend.styles._colors import (
    _ACCENT,
    _ACCENT_BG_22,
    _ACCENT_HI,
    _BG_OVERLAY,
    _BG_RAISED,
    _BG_SURFACE,
    _BORDER,
    _TEXT_MUTED,
    _TEXT_ON_ACCENT,
    _TEXT_PRI,
)
from frontend.icon_theme import themed_icon_path
from frontend.ui_tokens import (
    FONT_SIZE_LABEL,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_6,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SIZE_ITEM_SM,
    SPACE_10,
    SPACE_20,
    SPACE_6,
    SPACE_SM,
    SPACE_XS,
    SPACE_XXS,
    SPACE_XXXS,
)


def date_popup_styles() -> str:
    arrow_down = themed_icon_path("frontend/assets/icons/arrow_down.png")
    return f"""
QDateEdit::drop-down {{
    border: none;
    background: transparent;
    width: {SPACE_20}px;
}}
QDateEdit::down-arrow {{
    image: url({arrow_down});
    width: {SPACE_10}px;
    height: {SPACE_10}px;
}}
QCalendarWidget {{
    background: {_BG_SURFACE};
    border: {SPACE_XXXS}px solid {_BORDER};
    border-radius: {RADIUS_LG}px;
}}
QCalendarWidget QWidget {{
    background-color: {_BG_SURFACE};
    color: {_TEXT_PRI};
    font-size: {FONT_SIZE_LABEL}px;
}}
QCalendarWidget #qt_calendar_navigationbar {{
    background: {_BG_RAISED};
    border-top-left-radius: {RADIUS_LG}px;
    border-top-right-radius: {RADIUS_LG}px;
    border-bottom: none;
    padding: {SPACE_XXS}px {SPACE_6}px;
}}
QCalendarWidget QToolButton {{
    background: transparent;
    color: {_TEXT_PRI};
    border: none;
    border-radius: {RADIUS_6}px;
    padding: {SPACE_XS}px {SPACE_SM}px;
    min-height: {SIZE_ITEM_SM}px;
    font-weight: {FONT_WEIGHT_SEMIBOLD};
    font-size: {FONT_SIZE_LABEL}px;
    text-decoration: none;
}}
QCalendarWidget QToolButton:hover {{
    background: {_BG_OVERLAY};
}}
QCalendarWidget QToolButton:pressed {{
    background: {_ACCENT_BG_22};
}}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {{
    color: {_ACCENT_HI};
    min-width: {SPACE_20}px;
    padding: {SPACE_XS}px {SPACE_10}px;
}}
QCalendarWidget QToolButton::menu-indicator {{
    image: none;
    width: 0;
}}
QCalendarWidget QSpinBox {{
    background: {_BG_RAISED};
    color: {_TEXT_PRI};
    border: {SPACE_XXXS}px solid {_BORDER};
    border-radius: {RADIUS_SM}px;
    padding: {SPACE_XXS}px {SPACE_6}px;
    selection-background-color: {_ACCENT};
    selection-color: {_TEXT_ON_ACCENT};
}}
QCalendarWidget QMenu {{
    background: {_BG_OVERLAY};
    color: {_TEXT_PRI};
    border: {SPACE_XXXS}px solid {_BORDER};
}}
QCalendarWidget QAbstractItemView {{
    background-color: {_BG_SURFACE};
    color: {_TEXT_PRI};
    selection-background-color: {_ACCENT};
    selection-color: {_TEXT_ON_ACCENT};
    outline: none;
    border: none;
}}
QCalendarWidget QTableView {{
    border: none;
    gridline-color: transparent;
    outline: none;
}}
QCalendarWidget QAbstractItemView::item {{
    text-align: center;
    border-radius: {RADIUS_MD}px;
    border: none;
    padding: {SPACE_XXS}px;
}}
QCalendarWidget QAbstractItemView::item:hover {{
    background: {_ACCENT_BG_22};
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: {_TEXT_MUTED};
}}
"""
