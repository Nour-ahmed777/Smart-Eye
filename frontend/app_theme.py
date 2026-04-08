from frontend.styles.theme_parts import build_dark_theme, build_sidebar_dark
from frontend.styles._colors import _TEXT_PRI

DARK_THEME = build_dark_theme()
SIDEBAR_DARK = build_sidebar_dark()


def get_theme(name="dark"):
    return DARK_THEME + SIDEBAR_DARK


def safe_set_point_size(qfont, size, default=12):
    try:
        s = int(size)
    except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
        s = default
    if s <= 0:
        s = default
    qfont.setPointSize(s)


def page_base_styles(font_size: int = 13) -> str:
    return f"""
    QWidget {{
        color: {_TEXT_PRI};
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        font-size: {font_size}px;
        background-color: transparent;
    }}
    QLabel {{
        background: transparent;
    }}
    """


THEME_REGISTRY = {
    "page_base": page_base_styles(),
}

