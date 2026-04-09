from frontend.styles._colors import _BG_OVERLAY, _BG_RAISED, _BORDER, _BORDER_DIM
from frontend.ui_tokens import RADIUS_MD, SPACE_XXXS


_CARD_BASE = f"QFrame {{    background: {_BG_RAISED};    border: {SPACE_XXXS}px solid {_BORDER_DIM};    border-radius: {RADIUS_MD}px;}}"

_CARD_HOVER = f"QFrame:hover {{    border-color: {_BORDER};    background: {_BG_OVERLAY};}}"

_PANEL_BASE = f"QFrame {{    background: {_BG_RAISED};    border: {SPACE_XXXS}px solid {_BORDER};    border-radius: {RADIUS_MD}px;}}"
