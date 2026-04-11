from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Property, Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QAbstractButton, QSizePolicy

from frontend.styles._colors import _ACCENT, _BG_OVERLAY, _BORDER_DARK, _TEXT_ON_ACCENT, _TEXT_SEC, _TOGGLE_CIRCLE
from frontend.ui_tokens import SPACE_3

_PAD = SPACE_3


class ToggleSwitch(QAbstractButton):
    def __init__(
        self,
        width: int = 42,
        height: int = 22,
        bg_color: str = _BG_OVERLAY,
        circle_color: str = _TOGGLE_CIRCLE,
        active_color: str = _ACCENT,
        parent=None,
    ):
        super().__init__(parent)
        self.setCheckable(True)
        self._w = width
        self._h = height
        self._pad = _PAD
        self.setFixedSize(width + 2 * _PAD, height + 2 * _PAD)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color

        self._circle_position = _PAD + 3
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(QEasingCurve.Type.OutBack)
        self.animation.setDuration(200)

        self.toggled.connect(self._on_state_change)

    def _thumb_pos_for_state(self, checked: bool) -> int:
        return (self._pad + self._w - self._h + 3) if checked else (self._pad + 3)

    def _on_state_change(self, state):
        self.animation.stop()
        self.animation.setStartValue(self._circle_position)
        end = self._thumb_pos_for_state(bool(state))
        self.animation.setEndValue(end)
        self.animation.start()

    def setChecked(self, checked):
        prev = self.isChecked()
        super().setChecked(checked)
        # If signals are blocked, `toggled` will not fire, so keep the thumb in sync.
        if self.signalsBlocked() and prev != bool(checked):
            self.animation.stop()
            self.set_circle_position(self._thumb_pos_for_state(bool(checked)))

    def get_circle_position(self):
        return self._circle_position

    def set_circle_position(self, pos):
        self._circle_position = pos
        self.update()

    circle_position = Property(int, get_circle_position, set_circle_position)

    def sizeHint(self):
        return QSize(self._w + 2 * self._pad, self._h + 2 * self._pad)

    def minimumSizeHint(self):
        return QSize(self._w + 2 * self._pad, self._h + 2 * self._pad)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        w, h = self._w, self._h
        pad = self._pad
        radius = h // 2
        checked = self.isChecked()

        if checked:
            track = QColor(self._active_color)
            track.setAlpha(60)
        else:
            track = QColor(self._bg_color)

        p.setBrush(track)
        p.drawRoundedRect(pad + 0.5, pad + 0.5, w - 1, h - 1, radius - 0.5, radius - 0.5)

        if checked:
            border = QColor(self._active_color)
            border.setAlpha(180)
        else:
            border = QColor(_BORDER_DARK)

        p.setPen(QPen(border, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(pad + 0.5, pad + 0.5, w - 1, h - 1, radius - 0.5, radius - 0.5)
        p.setPen(Qt.PenStyle.NoPen)

        cx = self._circle_position
        cy = pad + 3
        cd = h - 6

        if checked:
            from PySide6.QtCore import QPointF

            glow = QRadialGradient(QPointF(cx + cd / 2, cy + cd / 2), cd * 1.1)
            ac = QColor(self._active_color)
            glow.setColorAt(0.0, QColor(ac.red(), ac.green(), ac.blue(), 80))
            glow.setColorAt(1.0, QColor(ac.red(), ac.green(), ac.blue(), 0))
            p.setBrush(glow)
            p.drawEllipse(cx - 3, cy - 3, cd + 6, cd + 6)

        thumb = QColor(_TEXT_ON_ACCENT if checked else _TEXT_SEC)
        p.setBrush(thumb)
        p.drawEllipse(cx, cy, cd, cd)

        p.end()
