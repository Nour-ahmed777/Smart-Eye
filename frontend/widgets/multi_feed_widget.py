import logging
import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget

from frontend.app_theme import safe_set_point_size
from frontend.styles._colors import _TEXT_SEC, _BG_SURFACE
from frontend.ui_tokens import (
    FONT_SIZE_HEADING,
    RADIUS_MD,
    SPACE_6,
)
from frontend.widgets.video_widget import VideoWidget

logger = logging.getLogger(__name__)


class MultiFeedWidget(QWidget):
    count_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACE_6)
        self._widgets = {}

        self._grid_size = 0
        self._last_rows = 1
        self._last_cols = 1
        self._empty_label = QLabel("No cameras started\n\nClick Start All to begin")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._empty_label.setStyleSheet(
            f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_HEADING}px; background: {_BG_SURFACE}; border-radius: {RADIUS_MD}px;"
        )
        f = QFont()
        safe_set_point_size(f, 13)
        self._empty_label.setFont(f)
        self._layout.addWidget(self._empty_label, 0, 0)
        self._layout.setRowStretch(0, 1)
        self._layout.setColumnStretch(0, 1)

    def set_grid_size(self, size):

        try:
            self._grid_size = int(size)
        except (TypeError, ValueError):
            logger.debug("Invalid grid size provided: %r", size, exc_info=True)
            self._grid_size = 0
        self._rearrange()

    def add_feed(self, camera_id, name: str = ""):
        if camera_id in self._widgets:
            return self._widgets[camera_id]
        widget = VideoWidget(camera_name=name)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        widget.setMinimumSize(240, 180)
        self._widgets[camera_id] = widget
        if self._empty_label.parent() is not None:
            self._layout.removeWidget(self._empty_label)
            self._empty_label.setParent(None)
        self._rearrange()
        return widget

    def remove_feed(self, camera_id):
        if camera_id in self._widgets:
            widget = self._widgets.pop(camera_id)
            self._layout.removeWidget(widget)
            widget.deleteLater()
            self._rearrange()

    def get_widget(self, camera_id):
        return self._widgets.get(camera_id)

    def get_ids(self):
        return list(self._widgets.keys())

    def update_frame(self, camera_id, frame, state=None):
        widget = self._widgets.get(camera_id)
        if widget:
            widget.update_frame(frame, state)

    def _rearrange(self):
        while self._layout.count():
            self._layout.takeAt(0)

        for r in range(self._last_rows):
            self._layout.setRowStretch(r, 0)
        for c in range(self._last_cols):
            self._layout.setColumnStretch(c, 0)

        cam_ids = list(self._widgets.keys())
        if not cam_ids:
            self._layout.addWidget(self._empty_label, 0, 0)
            self._layout.setRowStretch(0, 1)
            self._layout.setColumnStretch(0, 1)
            self._last_rows = 1
            self._last_cols = 1
            self.count_changed.emit(0)
            return

        for w in self._widgets.values():
            w.show()

        if self._grid_size and self._grid_size > 0:
            actual_cols = min(self._grid_size, len(cam_ids))
        else:
            actual_cols = max(1, min(len(cam_ids), int(math.ceil(math.sqrt(len(cam_ids))))))
        rows = max(1, (len(cam_ids) + actual_cols - 1) // actual_cols)

        for idx, cid in enumerate(cam_ids):
            r = idx // actual_cols
            c = idx % actual_cols
            self._layout.addWidget(self._widgets[cid], r, c)

        for r in range(rows):
            self._layout.setRowStretch(r, 1)
        for c in range(actual_cols):
            self._layout.setColumnStretch(c, 1)
        self._last_rows = rows
        self._last_cols = actual_cols
        self.count_changed.emit(len(cam_ids))

    def clear_all(self):
        for cid in list(self._widgets.keys()):
            self.remove_feed(cid)
