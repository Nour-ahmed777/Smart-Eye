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
        self._plot_widget.showGrid(x=True, y=True, alpha=0.15)
        layout.addWidget(self._plot_widget)
        self._plot_items = []
        self._empty_item = None

    def set_line_data(self, x, y, name="", color=_ACCENT, width=2):
        pen = pg.mkPen(color=color, width=width)
        item = self._plot_widget.plot(x, y, pen=pen, name=name)
        self._plot_items.append(item)
        return item

    def set_bar_data(self, x, y, color=_SUCCESS_DIM, width=0.6):
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
            self._empty_item = None

    def set_labels(self, left="", bottom=""):
        self._plot_widget.setLabel("left", left, color=_TEXT_SEC)
        self._plot_widget.setLabel("bottom", bottom, color=_TEXT_SEC)

    def set_x_ticks(self, ticks):
        axis = self._plot_widget.getAxis("bottom")
        axis.setTicks([list(enumerate(ticks))])

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
