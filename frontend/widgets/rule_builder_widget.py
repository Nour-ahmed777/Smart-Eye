from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from frontend.styles._btn_styles import _ICON_BTN_DANGER
from frontend.ui_tokens import (
    SIZE_CONTROL_32,
    SIZE_CONTROL_MD,
    SIZE_FIELD_W,
    SIZE_FIELD_W_SM,
    SIZE_BTN_W_80,
    SPACE_XS,
)


class ConditionRow(QWidget):
    removed = Signal(object)
    changed = Signal()

    def __init__(self, attributes=None, parent=None):
        super().__init__(parent)
        self._attributes = attributes or []
        self._value_choices = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, SPACE_XS, 0, SPACE_XS)
        self.attr_combo = QComboBox()
        self.attr_combo.setMinimumWidth(SIZE_FIELD_W)
        if attributes:
            self.attr_combo.addItems(attributes)
        self.attr_combo.currentTextChanged.connect(self._on_attr_changed)
        layout.addWidget(self.attr_combo)
        self.op_combo = QComboBox()
        self.op_combo.addItems(["eq", "neq", "gte", "lte"])
        self.op_combo.setMinimumWidth(SIZE_BTN_W_80)
        self.op_combo.currentTextChanged.connect(lambda: self.changed.emit())
        layout.addWidget(self.op_combo)

        self._value_container = QHBoxLayout()
        self.value_widget = QLineEdit()
        self.value_widget.setPlaceholderText("Value")
        self.value_widget.setMinimumWidth(SIZE_FIELD_W_SM)
        self.value_widget.textChanged.connect(lambda: self.changed.emit())
        self._value_container.addWidget(self.value_widget)
        layout.addLayout(self._value_container)
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(SIZE_CONTROL_32, SIZE_CONTROL_32)
        remove_btn.setStyleSheet(_ICON_BTN_DANGER)
        remove_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(remove_btn)

    def set_value_choices(self, choices: dict):
        self._value_choices = choices or {}

    def _on_attr_changed(self):
        attr = self.attr_combo.currentText()

        if attr in ("object", "objects", "identity"):
            vals = list(self._value_choices.get(attr, []))
            combo = QComboBox()
            combo.setMinimumWidth(SIZE_FIELD_W_SM)
            combo.addItem("")
            combo.addItems(vals)

            self._replace_value_widget(combo)
            combo.currentTextChanged.connect(lambda: self.changed.emit())
        else:
            if not isinstance(self.value_widget, QLineEdit):
                le = QLineEdit()
                le.setPlaceholderText("Value")
                le.setMinimumWidth(SIZE_FIELD_W_SM)
                le.textChanged.connect(lambda: self.changed.emit())
                self._replace_value_widget(le)
        self.changed.emit()

    def _replace_value_widget(self, new_widget):

        while self._value_container.count():
            item = self._value_container.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self.value_widget = new_widget
        self._value_container.addWidget(self.value_widget)

    def get_data(self):
        val = ""
        if isinstance(self.value_widget, QLineEdit):
            val = self.value_widget.text()
        else:
            try:
                val = self.value_widget.currentText()
            except AttributeError:
                val = ""
        return {
            "attribute": self.attr_combo.currentText(),
            "operator": self.op_combo.currentText(),
            "value": val,
        }

    def set_data(self, attribute, operator, value):
        idx = self.attr_combo.findText(attribute)
        if idx >= 0:
            self.attr_combo.setCurrentIndex(idx)
        idx = self.op_combo.findText(operator)
        if idx >= 0:
            self.op_combo.setCurrentIndex(idx)

        self._on_attr_changed()
        if isinstance(self.value_widget, QLineEdit):
            self.value_widget.setText(value)
        else:
            idx = self.value_widget.findText(value)
            if idx >= 0:
                self.value_widget.setCurrentIndex(idx)
            else:
                if value:
                    self.value_widget.addItem(value)
                    self.value_widget.setCurrentText(value)


class RuleBuilderWidget(QWidget):
    conditions_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attributes = []
        self._value_choices = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._conditions_layout = QVBoxLayout()
        layout.addLayout(self._conditions_layout)
        add_btn = QPushButton("+ Add Condition")
        add_btn.setProperty("class", "secondary")
        add_btn.setFixedHeight(SIZE_CONTROL_MD)
        add_btn.clicked.connect(self.add_condition)
        layout.addWidget(add_btn)
        self._rows = []

    def set_attributes(self, attributes):
        self._attributes = attributes

        for row in self._rows:
            cur = row.attr_combo.currentText()
            row.attr_combo.clear()
            row.attr_combo.addItems(self._attributes)

            if cur:
                idx = row.attr_combo.findText(cur)
                if idx >= 0:
                    row.attr_combo.setCurrentIndex(idx)

    def set_value_choices(self, choices: dict):
        self._value_choices = choices or {}
        for row in self._rows:
            row.set_value_choices(self._value_choices)

            row._on_attr_changed()

    def add_condition(self, attribute="", operator="eq", value=""):
        row = ConditionRow(self._attributes)
        row.set_value_choices(self._value_choices)
        if attribute:
            row.set_data(attribute, operator, value)
        row.removed.connect(self._remove_condition)
        row.changed.connect(lambda: self.conditions_changed.emit())
        self._conditions_layout.addWidget(row)
        self._rows.append(row)
        self.conditions_changed.emit()

    def _remove_condition(self, row):
        if row in self._rows:
            self._rows.remove(row)
            self._conditions_layout.removeWidget(row)
            row.deleteLater()
            self.conditions_changed.emit()

    def get_all_conditions(self):
        return [row.get_data() for row in self._rows]

    def clear(self):
        for row in self._rows[:]:
            self._conditions_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()
