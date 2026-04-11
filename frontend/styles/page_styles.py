from __future__ import annotations

from frontend.styles._colors import (
    _ACCENT_HI_BG_22,
    _ACCENT_HI_BG_45,
    _BG_BASE,
    _BG_OVERLAY,
    _BG_RAISED,
    _BG_SURFACE,
    _BORDER_DARK,
    _BORDER_DIM,
    _TEXT_MUTED,
    _TEXT_PRI,
)
from frontend.ui_tokens import (
    FONT_SIZE_CAPTION,
    FONT_SIZE_MICRO,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_HEAVY,
    RADIUS_3,
    RADIUS_11,
    RADIUS_LG,
    RADIUS_MD,
    SIZE_CONTROL_SM,
    SPACE_6,
    SPACE_14,
    SPACE_XXS,
    SPACE_XXXS,
)


def header_bar_style(widget_id: str | None = None, bg: str = _BG_BASE, border: str = _BORDER_DIM) -> str:
    base = f"background: {bg}; border-bottom: none;"
    if widget_id:
        return f"QWidget#{widget_id} {{ {base} }}"
    return base


def toolbar_style(bg: str = _BG_SURFACE, border: str = _BORDER_DIM) -> str:
    return f"background: {bg}; border-bottom: none;"


def splitter_handle_style(color: str = _BORDER_DIM, width: int = SPACE_XXXS) -> str:
    return f"QSplitter::handle {{ background-color: {color}; width: {width}px; }}"


def divider_style(color: str = _BORDER_DIM, height: int = SPACE_XXXS) -> str:
    return f"background: {color}; border: none; max-height: {height}px;"


def card_shell_style(bg: str = _BG_RAISED, radius: int = RADIUS_LG, border: str | None = None) -> str:
    if border:
        return f"background: {bg}; border-radius: {radius}px; border: {SPACE_XXXS}px solid {border};"
    return f"background: {bg}; border-radius: {radius}px;"


def section_kicker_style(color: str = _TEXT_MUTED) -> str:
    return (
        f"color: {color}; "
        f"font-size: {FONT_SIZE_MICRO}px; "
        f"font-weight: {FONT_WEIGHT_HEAVY}; "
        f"letter-spacing: {SPACE_XXXS}px;"
    )


def transparent_surface_style() -> str:
    return "background: transparent;"


def muted_label_style(color: str = _TEXT_MUTED, size: int = FONT_SIZE_CAPTION, weight: int | None = None) -> str:
    weight_part = f" font-weight: {weight};" if weight is not None else ""
    return f"color: {color}; font-size: {size}px;{weight_part}"


def text_style(color: str, *, size: int | None = None, weight: int | None = None, extra: str = "") -> str:
    parts = [f"color: {color};"]
    if size is not None:
        parts.append(f" font-size: {size}px;")
    if weight is not None:
        parts.append(f" font-weight: {weight};")
    if extra:
        parts.append(f" {extra}")
    return "".join(parts)


def neutral_badge_style() -> str:
    return (
        f"background: {_BG_OVERLAY}; color: {_TEXT_MUTED};"
        f" border-radius: {RADIUS_11}px; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_BOLD};"
    )


def filter_tool_button_style() -> str:
    return (
        "QToolButton {"
        f" background: {_BG_OVERLAY};"
        f" border: {SPACE_XXXS}px solid {_BORDER_DARK};"
        f" border-radius: {RADIUS_MD}px;"
        f" padding: 0 {SPACE_14}px;"
        f" color: {_TEXT_PRI};"
        "}"
        f"QToolButton:hover {{ background: {_BG_SURFACE}; }}"
        f"QToolButton:pressed {{ background: {_BG_OVERLAY}; }}"
        "QToolButton::menu-indicator { image: none; }"
    )


def saved_clips_scrollbar_style(*, scroll_area_bg: str | None = None) -> str:
    area_bg = f"background: {scroll_area_bg};" if scroll_area_bg else "background: transparent;"
    return f"""
QScrollArea {{ border: none; {area_bg} }}
QScrollBar:vertical {{ border: none; background: transparent; width: {SPACE_6}px; margin: {SPACE_XXS}px 0; }}
QScrollBar::handle:vertical {{
    background: {_ACCENT_HI_BG_22}; min-height: {SIZE_CONTROL_SM}px; border-radius: {RADIUS_3}px;
}}
QScrollBar::handle:vertical:hover {{ background: {_ACCENT_HI_BG_45}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""
