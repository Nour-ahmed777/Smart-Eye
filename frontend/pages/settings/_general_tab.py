from __future__ import annotations

import logging

from PySide6.QtCore import Signal, QPropertyAnimation
from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QFrame,
    QGraphicsOpacityEffect,
)

from backend.repository import db
from frontend.widgets.toggle_switch import ToggleSwitch
from frontend.styles._colors import _SUCCESS
from frontend.ui_tokens import (
    FONT_SIZE_LABEL,
    FONT_WEIGHT_BOLD,
    SIZE_BTN_W_100,
    SIZE_BTN_W_160,
    SPACE_10,
    SPACE_20,
    SPACE_MD,
    SPACE_XL,
)

from ._constants import (
    _DANGER_BTN,
    _FIELD_H,
    _PRIMARY_BTN,
    _make_sdiv,
    _srow,
)

logger = logging.getLogger(__name__)


class GeneralTab(QWidget):
    settings_saved = Signal()
    debug_mode_changed = Signal(bool)
    experimental_mode_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, SPACE_XL)
        bl.setSpacing(0)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        bl.addWidget(_make_sdiv("Startup"))

        self._autostart_toggle = ToggleSwitch()
        bl.addWidget(
            _srow(
                "Auto-start cameras",
                self._autostart_toggle,
                hint="Cameras marked as active will start streaming on application launch.",
            )
        )

        self._minimize_tray_toggle = ToggleSwitch()
        bl.addWidget(
            _srow(
                "Minimize to tray",
                self._minimize_tray_toggle,
                hint="Closing the window sends the app to the system tray instead of quitting.",
            )
        )

        bl.addWidget(_make_sdiv("Data"))

        self._log_retention = QSpinBox()
        self._log_retention.setRange(1, 365)
        self._log_retention.setValue(30)
        self._log_retention.setSuffix(" days")
        self._log_retention.setFixedHeight(_FIELD_H)
        bl.addWidget(
            _srow(
                "Log retention",
                self._log_retention,
                hint="Event logs older than this are automatically purged.",
            )
        )

        bl.addWidget(_make_sdiv("Developer"))

        self._debug_toggle = ToggleSwitch()
        self._debug_toggle.toggled.connect(self.debug_mode_changed.emit)
        bl.addWidget(
            _srow(
                "Debugging mode",
                self._debug_toggle,
                hint="Show the Debug tab with developer tools, test-data flooding and diagnostics.",
            )
        )

        self._experimental_toggle = ToggleSwitch()
        self._experimental_toggle.toggled.connect(self.experimental_mode_changed.emit)
        bl.addWidget(
            _srow(
                "Experimental settings",
                self._experimental_toggle,
                hint="Show the Experimental tab with in-development features such as ghost bbox tuning.",
            )
        )

        bl.addStretch()

        bl.addWidget(self._make_action_bar())

    def _make_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: transparent;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(SPACE_20, SPACE_MD, SPACE_20, SPACE_MD)
        row.setSpacing(SPACE_10)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet(_DANGER_BTN)
        reset_btn.setFixedWidth(SIZE_BTN_W_160)
        reset_btn.clicked.connect(self._reset_general)
        row.addWidget(reset_btn)

        row.addStretch()

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{_SUCCESS};font-weight:{FONT_WEIGHT_BOLD};font-size:{FONT_SIZE_LABEL}px;")
        self._status_lbl.setContentsMargins(0, 0, 0, 0)
        self._status_lbl.setVisible(False)
        row.addWidget(self._status_lbl)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(_PRIMARY_BTN)
        save_btn.setFixedWidth(SIZE_BTN_W_100)
        save_btn.clicked.connect(self._save)
        row.addWidget(save_btn)
        return bar

    def _save(self) -> None:
        db.set_setting("log_retention_days", str(self._log_retention.value()))
        db.set_setting("auto_start_cameras", "1" if self._autostart_toggle.isChecked() else "0")
        db.set_setting("minimize_to_tray", "1" if self._minimize_tray_toggle.isChecked() else "0")
        debug_on = self._debug_toggle.isChecked()
        db.set_setting("debug_mode_enabled", "1" if debug_on else "0")
        exp_on = self._experimental_toggle.isChecked()
        db.set_setting("experimental_mode_enabled", "1" if exp_on else "0")
        self.settings_saved.emit()
        self.debug_mode_changed.emit(debug_on)
        self.experimental_mode_changed.emit(exp_on)
        if db.get_bool("ui_show_save_popups", False):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "Saved", "General settings saved.")
        else:
            self._flash_status("Saved")
            logger.info("General settings saved.")

    def _flash_status(self, text: str) -> None:
        self._status_lbl.setText(text)
        self._status_lbl.setVisible(True)
        effect = QGraphicsOpacityEffect(self._status_lbl)
        self._status_lbl.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self._status_lbl)
        anim.setDuration(1000)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(
            lambda: (
                self._status_lbl.setText(""),
                self._status_lbl.setGraphicsEffect(None),
                self._status_lbl.setVisible(False),
            )
        )
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _reset_general(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        ok = QMessageBox.question(
            self,
            "Reset settings",
            "Reset all settings to defaults? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        defaults = {
            "theme": {"value": "dark", "type": "string"},
            "gpu_enabled": {"value": "1", "type": "bool"},
            "max_cameras": {"value": "4", "type": "int"},
            "snapshot_on_alarm": {"value": "1", "type": "bool"},
            "face_similarity_threshold": {"value": "0.45", "type": "float"},
            "liveness_enabled": {"value": "0", "type": "bool"},
            "log_retention_days": {"value": "90", "type": "int"},
            "auto_start_cameras": {"value": "0", "type": "bool"},
            "minimize_to_tray": {"value": "0", "type": "bool"},
            "insightface_model_name": {"value": "buffalo_l", "type": "string"},
        }
        try:
            db.import_settings_json(defaults)
            self.load()
            QMessageBox.information(self, "Reset", "Settings restored to defaults.")
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError) as exc:
            logger.exception("Failed to reset settings")
            QMessageBox.critical(self, "Error", f"Failed to reset settings:\n{exc}")

    def load(self) -> None:
        self._log_retention.setValue(int(db.get_setting("log_retention_days", "30")))
        self._autostart_toggle.setChecked(db.get_bool("auto_start_cameras", False))
        self._minimize_tray_toggle.setChecked(db.get_bool("minimize_to_tray", False))
        self._debug_toggle.setChecked(db.get_bool("debug_mode_enabled", False))
        self._experimental_toggle.setChecked(db.get_bool("experimental_mode_enabled", False))

