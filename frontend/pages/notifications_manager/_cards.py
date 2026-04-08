from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
)

from backend.repository import db
from frontend.app_theme import safe_set_point_size
from frontend.widgets.toggle_switch import ToggleSwitch
from frontend.ui_tokens import (
    FONT_SIZE_CAPTION,
    FONT_SIZE_LABEL,
    RADIUS_MD,
    FONT_SIZE_MICRO,
    FONT_WEIGHT_BOLD,
    SPACE_6,
    SIZE_CONTROL_22,
    SIZE_CONTROL_MID,
    SPACE_3,
)
from frontend.styles._colors import (
    _ACCENT_BG_12,
    _ACCENT_HI,
    _PURPLE,
    _PURPLE_BG_12,
    _TEXT_MUTED,
    _TEXT_PRI,
    _TEXT_SEC,
)

from ._constants import _pill
from frontend.widgets.base.roster_card_base import (
    apply_roster_card_style,
    build_roster_card_layout,
)


class ProfileCard(QFrame):
    clicked = Signal(int)

    def __init__(
        self,
        profile: dict,
        is_active: bool = False,
        on_toggle_changed=None,
        parent=None,
    ):
        super().__init__(parent)
        self._profile_id = profile["id"]
        self._on_toggle = on_toggle_changed
        self._is_active = is_active
        self._build(profile, is_active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build(self, profile: dict, is_active: bool):
        ptype = profile.get("type", "email")
        enabled = bool(profile.get("enabled", 1))
        is_email = ptype == "email"
        tc = _ACCENT_HI if is_email else _PURPLE
        td = _ACCENT_BG_12 if is_email else _PURPLE_BG_12

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        apply_roster_card_style(self, "ProfileCard", is_active)
        left_layout, info, pills, right = build_roster_card_layout(self)

        badge = _pill("EMAIL" if is_email else "WEBHOOK", tc, td)
        badge.setStyleSheet(
            f"color: {tc}; background-color: {td}; border: none;"
            f" border-radius: {RADIUS_MD}px; padding: 0 {SPACE_6}px; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_BOLD};"
        )

        info.setSpacing(SPACE_3)
        left_layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignCenter)

        name_lbl = QLabel(profile.get("name", "Unnamed"))
        nf = QFont()
        safe_set_point_size(nf, FONT_SIZE_LABEL)
        nf.setBold(True)
        name_lbl.setFont(nf)
        name_lbl.setStyleSheet(f"color: {_TEXT_PRI if enabled else _TEXT_SEC}; background: transparent;")
        info.addWidget(name_lbl)

        ep_lbl = QLabel(profile.get("endpoint", ""))
        ep_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; background: transparent;")
        info.addWidget(ep_lbl)

        toggle = ToggleSwitch(width=SIZE_CONTROL_MID, height=SIZE_CONTROL_22)
        toggle.setChecked(enabled)
        toggle.toggled.connect(
            lambda v, pid=profile["id"]: (
                db.update_notification_profile(pid, enabled=1 if v else 0),
                self._on_toggle() if self._on_toggle else None,
            )
        )
        right.addWidget(toggle)
        self._toggle = toggle

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if child is not None and self._toggle.isAncestorOf(child):
                super().mousePressEvent(event)
                return
            self.clicked.emit(self._profile_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_active(self, active: bool) -> None:
        if self._is_active == active:
            return
        self._is_active = active
        apply_roster_card_style(self, "ProfileCard", active)
