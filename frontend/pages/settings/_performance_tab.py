from __future__ import annotations

import logging

from PySide6.QtCore import QPropertyAnimation
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QGraphicsOpacityEffect,
)

from backend.repository import db
from frontend.widgets.toggle_switch import ToggleSwitch
from frontend.styles._colors import _SUCCESS
from frontend.ui_tokens import (
    FONT_SIZE_LABEL,
    FONT_WEIGHT_BOLD,
    SIZE_BTN_W_100,
    SPACE_20,
    SPACE_MD,
    SPACE_XL,
)

from ._constants import (
    _FIELD_H,
    _PRIMARY_BTN,
    _combo_ss,
    _make_sdiv,
    _srow,
)

logger = logging.getLogger(__name__)


class PerformanceTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.load()

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

        bl.addWidget(_make_sdiv("GPU Acceleration"))

        self._gpu_toggle = ToggleSwitch()
        bl.addWidget(
            _srow(
                "Enable GPU",
                self._gpu_toggle,
                hint="GPU is auto-detected via ONNX Runtime providers. AMD uses ROCm; Intel/AMD on Windows use DirectML.",
            )
        )

        bl.addWidget(_make_sdiv("CPU & Threads"))

        self._max_threads = QSpinBox()
        self._max_threads.setRange(1, 32)
        self._max_threads.setValue(4)
        self._max_threads.setFixedHeight(_FIELD_H)
        bl.addWidget(
            _srow(
                "Max threads",
                self._max_threads,
                hint="Worker threads used for inference. Match to physical core count.",
            )
        )

        self._limit_resources = ToggleSwitch()
        bl.addWidget(
            _srow(
                "Limit resource usage",
                self._limit_resources,
                hint="Reduces thread count and lowers process priority to keep the system responsive.",
            )
        )

        bl.addWidget(_make_sdiv("Frame Processing"))

        self._frame_skip = QSpinBox()
        self._frame_skip.setRange(0, 30)
        self._frame_skip.setValue(0)
        self._frame_skip.setSuffix(" frames")
        self._frame_skip.setFixedHeight(_FIELD_H)
        bl.addWidget(
            _srow(
                "Frame skip",
                self._frame_skip,
                hint="Drop N display frames between each decoded frame. Reduces CPU/GPU load at the cost of visual smoothness.",
            )
        )

        self._detection_interval = QSpinBox()
        self._detection_interval.setRange(1, 30)
        self._detection_interval.setValue(3)
        self._detection_interval.setSuffix(" frames")
        self._detection_interval.setFixedHeight(_FIELD_H)
        bl.addWidget(
            _srow(
                "Detection interval",
                self._detection_interval,
                hint="Run inference every N display frames. "
                "1 = max accuracy / slowest.  3 = ~10 inferences/s at 30 fps (recommended for CPU).  "
                "1–2 with a GPU.",
            )
        )

        bl.addWidget(_make_sdiv("Video"))

        self._max_resolution = QComboBox()
        self._max_resolution.setStyleSheet(_combo_ss())
        self._max_resolution.addItems(["640x480", "1280x720", "1920x1080", "Original"])
        self._max_resolution.setFixedHeight(_FIELD_H)
        bl.addWidget(
            _srow(
                "Max resolution",
                self._max_resolution,
                hint="Frames are downscaled to this before inference. Lower = faster.",
            )
        )

        bl.addWidget(_make_sdiv("UI & Tabs"))

        self._pause_tabs = ToggleSwitch()
        bl.addWidget(
            _srow(
                "Pause inactive tabs",
                self._pause_tabs,
                hint="Stops timers and UI updates when a tab is not active.",
            )
        )

        self._unload_tabs = ToggleSwitch()
        bl.addWidget(
            _srow(
                "Unload heavy tabs on leave",
                self._unload_tabs,
                hint="Destroys video-heavy pages when you switch away to free memory.",
            )
        )

        self._unload_idle_min = QSpinBox()
        self._unload_idle_min.setRange(1, 60)
        self._unload_idle_min.setValue(5)
        self._unload_idle_min.setSuffix(" min")
        self._unload_idle_min.setFixedHeight(_FIELD_H)
        bl.addWidget(
            _srow(
                "Unload idle tabs after",
                self._unload_idle_min,
                hint="Idle tabs are unloaded after this many minutes.",
            )
        )

        self._auto_pause_live = ToggleSwitch()
        bl.addWidget(
            _srow(
                "Auto-stop live cameras when idle",
                self._auto_pause_live,
                hint="Stops all cameras when no monitoring tabs are active. Restarts when returning.",
            )
        )

        bl.addStretch()
        bl.addWidget(self._make_action_bar())

    def _make_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: transparent;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(SPACE_20, SPACE_MD, SPACE_20, SPACE_MD)
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
        db.set_setting("gpu_enabled", "1" if self._gpu_toggle.isChecked() else "0")
        db.set_setting("max_threads", str(self._max_threads.value()))
        db.set_setting("frame_skip", str(self._frame_skip.value()))
        db.set_setting("detection_interval", str(self._detection_interval.value()))
        db.set_setting("limit_resources", 1 if self._limit_resources.isChecked() else 0)
        db.set_setting("max_resolution", self._max_resolution.currentText())
        db.set_setting("ui_pause_inactive_tabs", 1 if self._pause_tabs.isChecked() else 0)
        db.set_setting("ui_unload_on_leave", 1 if self._unload_tabs.isChecked() else 0)
        db.set_setting("ui_unload_idle_min", str(self._unload_idle_min.value()))
        db.set_setting("auto_pause_live_when_idle", 1 if self._auto_pause_live.isChecked() else 0)

        try:
            from utils.resource_limiter import apply_limits

            apply_limits(
                bool(db.get_setting("limit_resources", False)),
                int(db.get_setting("max_threads", 1)),
            )
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            logger.exception("Failed to apply resource limits after save")

        try:
            from backend.models import model_loader

            model_loader.load_face_model()
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            logger.exception("Failed to reload face model after performance settings save")
        if db.get_bool("ui_show_save_popups", False):
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "Saved", "Performance settings saved.")
        else:
            self._flash_status("Saved")
            logger.info("Performance settings saved.")

    def _flash_status(self, text: str) -> None:
        self._status_lbl.setText(text)
        self._status_lbl.setVisible(True)
        eff = QGraphicsOpacityEffect(self._status_lbl)
        self._status_lbl.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self._status_lbl)
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

    def load(self) -> None:
        self._gpu_toggle.setChecked(db.get_bool("gpu_enabled", False))
        self._max_threads.setValue(int(db.get_int("max_threads", 4) or 4))
        self._frame_skip.setValue(int(db.get_int("frame_skip", 0) or 0))
        self._detection_interval.setValue(int(db.get_int("detection_interval", 3) or 3))
        self._limit_resources.setChecked(db.get_bool("limit_resources", False))
        max_res = db.get_setting("max_resolution", "Original")
        idx = self._max_resolution.findText(max_res)
        self._max_resolution.setCurrentIndex(idx if idx >= 0 else 0)

        self._pause_tabs.setChecked(db.get_bool("ui_pause_inactive_tabs", True))
        self._unload_tabs.setChecked(db.get_bool("ui_unload_on_leave", True))
        self._unload_idle_min.setValue(int(db.get_int("ui_unload_idle_min", 5) or 5))
        self._auto_pause_live.setChecked(db.get_bool("auto_pause_live_when_idle", False))

