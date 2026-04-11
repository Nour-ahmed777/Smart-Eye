from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QPushButton

from frontend.styles._btn_styles import _PRIMARY_BTN, _SECONDARY_BTN
from frontend.styles._colors import _SUCCESS
from frontend.ui_tokens import FONT_SIZE_LABEL, FONT_WEIGHT_BOLD, SIZE_CONTROL_MD


def build_status_label(color: str = _SUCCESS) -> QLabel:
    lbl = QLabel("")
    lbl.setStyleSheet(f"color:{color};font-weight:{FONT_WEIGHT_BOLD};font-size:{FONT_SIZE_LABEL}px;")
    lbl.setContentsMargins(0, 0, 0, 0)
    lbl.setVisible(False)
    return lbl


def flash_status(label: QLabel, text: str, duration_ms: int = 1000) -> None:
    label.setText(text)
    label.setVisible(True)
    eff = QGraphicsOpacityEffect(label)
    label.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", label)
    anim.setDuration(duration_ms)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)

    def _clear() -> None:
        label.setText("")
        label.setGraphicsEffect(None)
        label.setVisible(False)

    anim.finished.connect(_clear)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


def make_save_button(text: str = "Save") -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(SIZE_CONTROL_MD)
    btn.setStyleSheet(_PRIMARY_BTN)
    return btn


def make_close_button(text: str = "Close") -> QPushButton:
    btn = QPushButton(text)
    btn.setFixedHeight(SIZE_CONTROL_MD)
    btn.setStyleSheet(_SECONDARY_BTN)
    return btn
