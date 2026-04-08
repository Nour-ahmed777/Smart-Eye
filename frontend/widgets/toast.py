from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout, QWidget

from frontend.styles._colors import _ACCENT_HI_BG_40, _BG_RAISED_90, _TEXT_PRI
from frontend.ui_tokens import FONT_SIZE_LABEL, RADIUS_9, SPACE_10, SPACE_14, SPACE_XXXS


def show_toast(parent: QWidget, message: str, duration_ms: int = 1800) -> None:
    if parent is None:
        return

    toast = QFrame(parent)
    toast.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip | Qt.WindowType.WindowDoesNotAcceptFocus)
    toast.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    toast.setStyleSheet(
        f"""
        QFrame {{
            background: {_BG_RAISED_90};
            border: {SPACE_XXXS}px solid {_ACCENT_HI_BG_40};
            border-radius: {RADIUS_9}px;
        }}
        QLabel {{
            color: {_TEXT_PRI};
            padding: {SPACE_10}px {SPACE_14}px;
            font-size: {FONT_SIZE_LABEL}px;
        }}
        """
    )

    layout = QVBoxLayout(toast)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    lbl = QLabel(message, toast)
    lbl.setWordWrap(True)
    layout.addWidget(lbl)

    toast.adjustSize()

    try:
        parent_rect = parent.geometry()
        target = QPoint(
            parent_rect.left() + parent_rect.width() - toast.width() - 24,
            parent_rect.top() + parent_rect.height() - toast.height() - 24,
        )
        toast.move(parent.mapToGlobal(target))
    except (AttributeError, RuntimeError):
        pass

    toast.show()
    QTimer.singleShot(duration_ms, toast.close)
