import logging

import pyqtgraph as pg
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from frontend.styles._colors import _ACCENT, _BG_RAISED, _SUCCESS_DIM, _TEXT_MUTED, _TEXT_PRI, _TEXT_SEC
from frontend.ui_tokens import FONT_SIZE_SUBHEAD

logger = logging.getLogger(__name__)


class ChartWidget(QWidget):
    def __init__(self, title="", chart_type="line", parent=None):
        super().__init__(parent)
        self._chart_type = chart_type
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        pg.setConfigOptions(antialias=True)
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground(_BG_RAISED)

        if title:
            self._plot_widget.setTitle(title, color=_TEXT_PRI, size=f"{FONT_SIZE_SUBHEAD}pt")
            try:
                self._plot_widget.getPlotItem().titleLabel.setVisible(False)
            except (AttributeError, RuntimeError):
                logger.debug("Unable to hide chart title label", exc_info=True)
        self._plot_widget.getAxis("left").setPen(pg.mkPen(_TEXT_MUTED))
        self._plot_widget.getAxis("bottom").setPen(pg.mkPen(_TEXT_MUTED))
        self._plot_widget.getAxis("left").setTextPen(pg.mkPen(_TEXT_SEC))
        self._plot_widget.getAxis("bottom").setTextPen(pg.mkPen(_TEXT_SEC))
        self._plot_widget.getAxis("bottom").setStyle(autoExpandTextSpace=True, tickTextOffset=8)
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self._plot_widget)
        self._plot_items = []
        self._empty_item = None

    @staticmethod
    def _compact_tick_label(value) -> str:
        text = str(value or "")

        if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
            return text[5:10]
        return text

    def set_line_data(self, x, y, name="", color=_ACCENT, width=2):
        if self._empty_item is not None:
            self.clear_data()
        pen = pg.mkPen(color=color, width=width)
        item = self._plot_widget.plot(x, y, pen=pen, name=name)
        self._plot_items.append(item)
        return item

    def set_bar_data(self, x, y, color=_SUCCESS_DIM, width=0.6):
        if self._empty_item is not None:
            self.clear_data()
        bar = pg.BarGraphItem(x=x, height=y, width=width, brush=color)
        self._plot_widget.addItem(bar)
        self._plot_items.append(bar)
        return bar

    def set_data(self, x, y, **kwargs):
        if self._chart_type == "bar":
            return self.set_bar_data(x, y, **kwargs)
        return self.set_line_data(x, y, **kwargs)

    def clear_data(self):
        for item in self._plot_items:
            self._plot_widget.removeItem(item)
        self._plot_items.clear()
        if self._empty_item is not None:
            try:
                self._plot_widget.removeItem(self._empty_item)
            except (AttributeError, RuntimeError):
                logger.debug("Unable to remove empty-state item", exc_info=True)
            try:
                vb = self._plot_widget.getViewBox()
                vb.removeItem(self._empty_item)
            except (AttributeError, RuntimeError):
                logger.debug("Unable to remove empty-state item from viewbox", exc_info=True)
            self._empty_item = None

    def set_labels(self, left="", bottom=""):
        self._plot_widget.setLabel("left", left, color=_TEXT_SEC)
        self._plot_widget.setLabel("bottom", bottom, color=_TEXT_SEC)

    def set_x_ticks(self, ticks, max_labels: int = 8):
        axis = self._plot_widget.getAxis("bottom")
        if not ticks:
            axis.setTicks([[]])
            return

        total = len(ticks)
        if max_labels <= 1 or total <= max_labels:
            indices = list(range(total))
        else:
            spread = [round(i * (total - 1) / (max_labels - 1)) for i in range(max_labels)]
            indices = []
            seen = set()
            for idx in spread:
                i = int(max(0, min(total - 1, idx)))
                if i not in seen:
                    seen.add(i)
                    indices.append(i)
            if indices and indices[-1] != total - 1:
                indices.append(total - 1)

        axis.setTicks([[(idx, self._compact_tick_label(ticks[idx])) for idx in indices]])

    def set_title(self, title):
        self._plot_widget.setTitle(title, color=_TEXT_PRI, size=f"{FONT_SIZE_SUBHEAD}pt")

    def get_plot_widget(self):
        return self._plot_widget

    def clear_x_ticks(self):
        axis = self._plot_widget.getAxis("bottom")
        axis.setTicks([[]])

    def set_empty_state(self, text):
        self.clear_data()
        self.clear_x_ticks()
        if not text:
            return
        try:
            item = pg.TextItem(text=text, color=_TEXT_MUTED, anchor=(0.5, 0.5))
            vb = self._plot_widget.getViewBox()
            rect = vb.viewRect()
            if rect is not None:
                item.setPos(rect.center())
            vb.addItem(item)
            self._empty_item = item
        except (AttributeError, RuntimeError, TypeError, ValueError):
            logger.debug("Unable to set chart empty state", exc_info=True)
            self._empty_item = None
