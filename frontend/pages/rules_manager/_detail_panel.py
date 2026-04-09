from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from backend.repository import db
from frontend.services.rules_service import RulesService
from frontend.widgets.confirm_delete_button import ConfirmDeleteButton
from frontend.styles._colors import (
    _ACCENT_HI_BG_20,
    _BORDER_DIM_00,
    _BORDER_DIM_55,
)
from ._widgets import build_rule_header
from frontend.ui_tokens import (
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_WEIGHT_BOLD,
    SIZE_BTN_W_80,
    SIZE_BTN_W_MD,
    SIZE_CONTROL_MD,
    SIZE_LABEL_MIN,
    SIZE_LABEL_W,
    SPACE_10,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    SPACE_XXL,
    SPACE_XXS,
    SPACE_XXXS,
)

from ._constants import (
    _BORDER_DIM,
    _TEXT_BTN_BLUE,
    _TEXT_BTN_GHOST,
    _TEXT_BTN_RED,
    _TEXT_BTN_RED_CONFIRM,
    _TEXT_MUTED,
    _TEXT_PRI,
    _TEXT_SEC,
)


class RuleDetailPanel(QWidget):
    delete_requested = Signal(int)
    saved = Signal()
    close_requested = Signal()

    def __init__(self, parent=None, rules_service: RulesService | None = None):
        super().__init__(parent)
        self._rules_service = rules_service or RulesService()
        self._rule_id = None
        self._rule = None
        self._edit_widget = None
        self._build_empty()

    def _build_empty(self):
        self._clear()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;border:none;")
        wl = QVBoxLayout(wrap)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.setSpacing(SPACE_10)
        wl.setContentsMargins(SPACE_XXL, SPACE_XXL, SPACE_XXL, SPACE_XXL)

        t = QLabel("No rule selected")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"font-size:{FONT_SIZE_BODY}px;font-weight:{FONT_WEIGHT_BOLD};color:{_TEXT_SEC};")
        wl.addWidget(t)

        s = QLabel("Select a rule from the list to view its details, or create a new one.")
        s.setWordWrap(True)
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet(f"font-size:{FONT_SIZE_CAPTION}px;color:{_TEXT_MUTED};")
        wl.addWidget(s)
        lay.addWidget(wrap)

    def _clear(self):

        for w in self.findChildren(QWidget):
            w.setParent(None)
            w.deleteLater()
        old = self.layout()
        if old is not None:
            from shiboken6 import delete

            delete(old)

    def load_rule(self, rule: dict):
        self._rule_id = rule["id"]
        self._rule = rule
        self._edit_widget = None
        self._show_view(rule)

    def _show_view(self, rule: dict):
        self._clear()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        enabled = bool(rule.get("enabled", 1))
        action = rule.get("action", "log_only")
        logic = rule.get("logic", "AND")
        priority = int(rule.get("priority", 0))

        heat_level = priority
        try:
            _a = self._rules_service.get_alarm_actions(self._rule_id)
            if _a:
                heat_level = max(heat_level, max(int(a.get("escalation_level", 0) or 0) for a in _a) * 3)
        except (sqlite3.Error, RuntimeError, AttributeError, TypeError, ValueError):
            pass

        desc = (rule.get("description") or "").strip() or "No description"
        hero = build_rule_header(
            rule.get("name", ""),
            desc,
            action,
            logic,
            priority,
            heat_level,
            enabled,
            label="RULE",
            parent=self,
        )
        lay.addWidget(hero)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("border:none;background:transparent;")
        sb = QWidget()
        bl = QVBoxLayout(sb)
        bl.setContentsMargins(SPACE_XL, SPACE_LG, SPACE_XL, SPACE_LG)
        bl.setSpacing(SPACE_XXS)
        scroll.setWidget(sb)
        lay.addWidget(scroll, stretch=1)

        def _info_row(label, value):
            w = QWidget()
            w.setStyleSheet("background:transparent;border:none;")
            r = QHBoxLayout(w)
            r.setContentsMargins(0, SPACE_XS, 0, SPACE_XS)
            r.setSpacing(SPACE_10)
            lb = QLabel(f"{label}:")
            lb.setFixedWidth(SIZE_LABEL_W)
            lb.setStyleSheet(f"color:{_TEXT_SEC};font-size:{FONT_SIZE_LABEL}px;min-width:{SIZE_LABEL_MIN}px;")
            r.addWidget(lb)
            vl = QLabel(value if value else "\u2014")
            vl.setStyleSheet(
                f"color:{_TEXT_PRI};font-size:{FONT_SIZE_BODY}px;"
                if value
                else f"color:{_TEXT_MUTED};font-size:{FONT_SIZE_CAPTION}px;font-style:italic;"
            )
            vl.setWordWrap(True)
            r.addWidget(vl, stretch=1)
            return w

        def _div():
            d = QFrame()
            d.setFrameShape(QFrame.Shape.HLine)
            d.setStyleSheet(f"background:{_BORDER_DIM_55};border:none;max-height:{SPACE_XXXS}px;")
            return d

        def _section(title):
            c = QWidget()
            c.setStyleSheet("background:transparent;border:none;")
            r = QHBoxLayout(c)
            r.setContentsMargins(0, SPACE_SM, 0, SPACE_XXS)
            r.setSpacing(SPACE_SM)
            lb = QLabel(title.upper())
            lb.setStyleSheet(
                f"font-size:{FONT_SIZE_MICRO}px;font-weight:{FONT_WEIGHT_BOLD};color:{_TEXT_MUTED};letter-spacing:{SPACE_XXXS}px;"
            )
            r.addWidget(lb)
            ln = QFrame()
            ln.setFrameShape(QFrame.Shape.HLine)
            ln.setStyleSheet(
                "background:qlineargradient(spread:pad,x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 {_ACCENT_HI_BG_20},stop:1 {_BORDER_DIM_00});border:none;max-height:{SPACE_XXXS}px;"
            )
            r.addWidget(ln, stretch=1)
            return c

        def _cam_name(cid):
            if not cid:
                return "All Cameras"
            try:
                c = db.get_camera(cid)
                return c["name"] if c else f"Camera #{cid}"
            except (sqlite3.Error, RuntimeError, AttributeError, TypeError):
                return f"Camera #{cid}"

        def _zone_name(zid):
            if not zid:
                return "Whole Frame"
            try:
                for z in db.get_zones():
                    if z["id"] == zid:
                        return z["name"]
            except (sqlite3.Error, RuntimeError, AttributeError, TypeError):
                pass
            return f"Zone #{zid}"

        bl.addWidget(_section("General"))
        for lbl, val in [
            ("Camera", _cam_name(rule.get("camera_id"))),
            ("Zone", _zone_name(rule.get("zone_id"))),
            ("Logic", logic),
            ("Action", action),
            ("Priority", str(priority)),
        ]:
            bl.addWidget(_info_row(lbl, val))
            bl.addWidget(_div())

        bl.addSpacing(SPACE_10)
        bl.addWidget(_section("Conditions"))
        conds = db.get_rule_conditions(self._rule_id)
        if conds:
            for c in conds:
                bl.addWidget(_info_row(c.get("attribute", ""), f"{c.get('operator', 'eq')}  \u2192  {c.get('value', '')}"))
                bl.addWidget(_div())
        else:
            nl = QLabel("No conditions defined")
            nl.setStyleSheet(f"color:{_TEXT_MUTED};font-size:{FONT_SIZE_LABEL}px;font-style:italic;padding:{SPACE_XS}px 0;")
            bl.addWidget(nl)

        bl.addSpacing(SPACE_10)
        bl.addWidget(_section("Alarm Escalation"))
        alarms = db.get_alarm_actions(self._rule_id)
        if alarms:
            for a in alarms:
                summary = (
                    f"Level {a.get('escalation_level', 1)}  \u00b7  "
                    f"{a.get('action_type', '')}  \u00b7  "
                    f"delay {a.get('trigger_after_sec', 0)}s  \u00b7  "
                    f"cooldown {a.get('cooldown_sec', 0)}s"
                )
                bl.addWidget(_info_row(f"Escalation {a.get('escalation_level', 1)}", summary))
                bl.addWidget(_div())
        else:
            nl = QLabel("No alarm actions defined")
            nl.setStyleSheet(f"color:{_TEXT_MUTED};font-size:{FONT_SIZE_LABEL}px;font-style:italic;padding:{SPACE_XS}px 0;")
            bl.addWidget(nl)

        bl.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{_BORDER_DIM};border:none;max-height:{SPACE_XXXS}px;")
        lay.addWidget(sep)

        ab = QHBoxLayout()
        ab.setContentsMargins(SPACE_XL, SPACE_10, SPACE_XL, SPACE_MD)
        ab.setSpacing(SPACE_SM)
        del_btn = ConfirmDeleteButton("Delete", "Sure?")
        del_btn.setFixedHeight(SIZE_CONTROL_MD)
        del_btn.setFixedWidth(SIZE_BTN_W_MD)
        del_btn.set_button_styles(_TEXT_BTN_RED, _TEXT_BTN_RED_CONFIRM)
        del_btn.set_confirm_callback(lambda: self.delete_requested.emit(self._rule_id))
        ab.addWidget(del_btn)
        ab.addStretch()

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(SIZE_CONTROL_MD)
        close_btn.setFixedWidth(SIZE_BTN_W_80)
        close_btn.setStyleSheet(_TEXT_BTN_GHOST)
        close_btn.clicked.connect(lambda: self.close_requested.emit())
        ab.addWidget(close_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedHeight(SIZE_CONTROL_MD)
        edit_btn.setFixedWidth(SIZE_BTN_W_80)
        edit_btn.setStyleSheet(_TEXT_BTN_BLUE)
        edit_btn.clicked.connect(self._open_edit)
        ab.addWidget(edit_btn)
        lay.addLayout(ab)

    def _open_edit(self):
        if self._rule is None:
            return
        from ._forms import _EditRuleForm

        self._clear()
        self._edit_widget = _EditRuleForm(self._rule, self._rules_service)
        self._edit_widget.cancel_requested.connect(lambda: self.load_rule(self._rules_service.get_rule(self._rule_id)))
        self._edit_widget.delete_requested.connect(lambda: self.delete_requested.emit(self._rule_id))
        self._edit_widget.saved.connect(self._on_edit_saved)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._edit_widget)

    def _on_edit_saved(self):
        self.saved.emit()

    def clear(self):
        self._rule_id = None
        self._rule = None
        self._edit_widget = None
        self._build_empty()
