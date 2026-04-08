from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve
from PySide6.QtWidgets import (
    QLabel,
    QFrame,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QPainter, QColor, QPen

from frontend.styles._colors import (
    _BG_RAISED,
    _DANGER,
    _DANGER_BORDER_55,
    _TEXT_PRI,
)
from frontend.styles._shadows import apply_shadow_float
from frontend.ui_tokens import (
    FONT_SIZE_BODY,
    FONT_SIZE_HEADING,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_14,
    RADIUS_18,
    SIZE_DIALOG_W_MD,
    SIZE_OFFSET_LG,
    SPACE_18,
    SPACE_20,
    SPACE_6,
    SPACE_MD,
    SPACE_SM,
    SPACE_XXXS,
)


class AlertPopup(QFrame):
    def __init__(self, parent: QWidget, title: str, subtitle: str):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.ToolTip
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(SIZE_DIALOG_W_MD)

        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        apply_shadow_float(self, _DANGER)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.content_frame = QFrame(self)
        self.content_frame.setStyleSheet(
            """
            QFrame {{
                background: {bg};
                border: {border_w}px solid {border};
                border-radius: {radius}px;
            }}
            """.format(bg=_BG_RAISED, border_w=SPACE_XXXS, border=_DANGER_BORDER_55, radius=RADIUS_18)
        )

        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(SPACE_20, SPACE_18, SPACE_20, SPACE_18)
        content_layout.setSpacing(SPACE_SM)

        title_label = QLabel(title, self.content_frame)
        title_label.setStyleSheet(
            """
            QLabel {{
                color: {color};
                font-weight: {weight};
                font-size: {size}px;
                background: transparent;
                border: none;
            }}
            """.format(color=_DANGER, weight=FONT_WEIGHT_SEMIBOLD, size=FONT_SIZE_HEADING)
        )
        title_label.setWordWrap(True)
        content_layout.addWidget(title_label)

        subtitle_label = QLabel(subtitle, self.content_frame)
        subtitle_label.setStyleSheet(
            """
            QLabel {{
                color: {color};
                font-size: {size}px;
                background: transparent;
                border: none;
            }}
            """.format(color=_TEXT_PRI, size=FONT_SIZE_BODY)
        )
        subtitle_label.setWordWrap(True)
        content_layout.addWidget(subtitle_label)

        root.addWidget(self.content_frame)

        self.adjustSize()
        QTimer.singleShot(6500, self.close)
        self._anim = None

    def paintEvent(self, event):
        super().paintEvent(event)

        if not hasattr(self, "content_frame"):
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        frame_rect = self.content_frame.geometry()
        x = frame_rect.x()
        y = frame_rect.y()
        w = frame_rect.width()
        h = frame_rect.height()

        outline_color = QColor(_DANGER)
        outline_color.setAlphaF(0.24)
        painter.setPen(QPen(outline_color, 1.3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x + SPACE_6, y + SPACE_6, w - SPACE_MD, h - SPACE_MD, RADIUS_14, RADIUS_14)

    def closeEvent(self, event):
        super().closeEvent(event)


def show_alert(parent: QWidget, title: str, subtitle: str, offset: int = 12) -> None:
    if parent is None:
        return
    popup = AlertPopup(parent, title, subtitle)
    try:
        rect = parent.geometry()
        x = rect.left() + offset
        y = rect.top() + offset
        end_pos = parent.mapToGlobal(QPoint(x, y))
        start_pos = QPoint(end_pos.x() - SIZE_OFFSET_LG, end_pos.y())
        popup.move(start_pos)
        popup.show()
        anim = QPropertyAnimation(popup, b"pos", popup)
        anim.setDuration(700)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(start_pos)
        anim.setEndValue(end_pos)
        popup._anim = anim
        anim.start()
    except (AttributeError, RuntimeError):
        popup.move(parent.mapToGlobal(QPoint(0, 0)))
