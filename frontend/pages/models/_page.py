from __future__ import annotations

import contextlib
import logging
import os
import sqlite3

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QSettings
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QGraphicsOpacityEffect,
)

from backend.repository import db
from backend.pipeline.detector_manager import get_manager, notify_plugins_changed
from frontend.app_theme import safe_set_point_size
from frontend.widgets.toggle_switch import ToggleSwitch
from frontend.widgets.toast import show_toast
from frontend.styles._colors import (
    _ACCENT,
    _ACCENT_BG_22,
    _ACCENT_HI_BG_28,
    _ACCENT_HI_BG_55,
    _BG_BASE,
    _BG_OVERLAY,
    _BG_RAISED,
    _BG_SURFACE,
    _BORDER,
    _BORDER_DIM,
    _CLASS_COLOR_1,
    _CLASS_COLOR_2,
    _CLASS_COLOR_3,
    _CLASS_COLOR_4,
    _CLASS_COLOR_5,
    _CLASS_COLOR_6,
    _CLASS_COLOR_7,
    _CLASS_COLOR_8,
    _DANGER,
    _SUCCESS,
    _TEXT_MUTED,
    _TEXT_PRI,
    _TEXT_SEC,
    _WARNING_ORANGE,
)
from frontend.styles._input_styles import _FORM_INPUTS, _FORM_COMBO
from frontend.styles._btn_styles import (
    _PRIMARY_BTN,
    _TEXT_BTN_RED as _RED_TXT_BTN,
    _TAB_BTN as _M_TAB_BTN,
    _TAB_BTN_ACTIVE as _M_TAB_BTN_ACTIVE,
)
from frontend.styles.page_styles import header_bar_style, toolbar_style
from frontend.ui_tokens import (
    FONT_SIZE_BODY,
    FONT_SIZE_CAPTION,
    FONT_SIZE_LABEL,
    FONT_SIZE_LARGE,
    FONT_SIZE_MICRO,
    FONT_SIZE_SUBHEAD,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_HEAVY,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_6,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SIZE_BTN_W_100,
    SIZE_BTN_W_160,
    SIZE_BTN_W_55,
    SIZE_BTN_W_72,
    SIZE_BTN_W_LG,
    SIZE_BTN_W_SM,
    SIZE_CONTROL_22,
    SIZE_CONTROL_38,
    SIZE_CONTROL_LG,
    SIZE_CONTROL_MD,
    SIZE_CONTROL_SM,
    SIZE_FIELD_W,
    SIZE_FIELD_W_SM,
    SIZE_HEADER_H,
    SIZE_ITEM_SM,
    SIZE_PILL_H,
    SIZE_ROW_48,
    SIZE_ROW_MD,
    SIZE_SECTION_H,
    SPACE_10,
    SPACE_14,
    SPACE_18,
    SPACE_20,
    SPACE_28,
    SPACE_5,
    SPACE_6,
    SPACE_LG,
    SPACE_MD,
    SPACE_SM,
    SPACE_XL,
    SPACE_XS,
    SPACE_XXS,
    SPACE_XXXS,
)

logger = logging.getLogger(__name__)
_STYLESHEET = f"""
QWidget {{
    color: {_TEXT_PRI};
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: {FONT_SIZE_BODY}px; background-color: transparent;
}}
QLabel {{ background: transparent; }}
QScrollArea {{ border: none; background: transparent; }}
{_FORM_INPUTS}
{_FORM_COMBO}
QScrollBar:vertical {{ border: none; background: transparent; width: {SPACE_SM}px; margin: {SPACE_XXS}px {SPACE_XXXS}px; }}
QScrollBar::handle:vertical {{
    background: {_ACCENT_HI_BG_28}; min-height: {SPACE_28}px; border-radius: {RADIUS_SM}px;
}}
QScrollBar::handle:vertical:hover {{ background: {_ACCENT_HI_BG_55}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QCheckBox {{ color: {_TEXT_PRI}; spacing: {SPACE_SM}px; }}
QCheckBox::indicator {{
    width: {SPACE_LG}px; height: {SPACE_LG}px; border: {SPACE_XXXS}px solid {_BORDER};
    border-radius: {RADIUS_SM}px; background-color: {_BG_RAISED};
    image: none;
}}
QCheckBox::indicator:checked {{
    background-color: {_ACCENT}; border-color: {_ACCENT};
    image: url(frontend/assets/icons/checkmark.png);
}}
"""


def _sec_div(title: str) -> QWidget:
    fr = QWidget()
    fr.setFixedHeight(SIZE_CONTROL_38)
    fr.setStyleSheet(f"background: {_BG_BASE};")
    row = QHBoxLayout(fr)
    row.setContentsMargins(SPACE_XL, 0, SPACE_LG, 0)
    lbl = QLabel(title.upper())
    lbl.setStyleSheet(
        f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY};"
        f" letter-spacing: 1.{SPACE_5}px; background: transparent;"
    )
    row.addWidget(lbl)
    row.addStretch()
    return fr


def _field_row(label: str, widget: QWidget, label_w: int = 140) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(SPACE_MD)
    lbl = QLabel(label)
    lbl.setFixedWidth(label_w)
    lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_LABEL}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
    row.addWidget(lbl)
    row.addWidget(widget, stretch=1)
    return row


def _default_class_color(cls_name: str) -> str:
    _colors = [
        _CLASS_COLOR_1,
        _CLASS_COLOR_2,
        _CLASS_COLOR_3,
        _CLASS_COLOR_4,
        _CLASS_COLOR_5,
        _CLASS_COLOR_6,
        _CLASS_COLOR_7,
        _CLASS_COLOR_8,
    ]
    return _colors[hash(cls_name) % len(_colors)]


class ModelsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_STYLESHEET)
        self._ap_extracted_classes: list = []
        self._fm_reload_busy = False
        self._fm_load_worker = None
        self._fm_progress = None
        self._fm_reload_timer = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header_w = QWidget()
        header_w.setFixedHeight(SIZE_HEADER_H)
        header_w.setStyleSheet(header_bar_style(bg=_BG_BASE, border=_BORDER_DIM))
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(SPACE_XL, 0, SPACE_XL, 0)
        hl.setSpacing(SPACE_MD)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(SIZE_CONTROL_SM, SIZE_CONTROL_SM)
        _pix = QPixmap("frontend/assets/icons/object.png")
        if not _pix.isNull():
            icon_lbl.setPixmap(
                _pix.scaled(
                    SIZE_CONTROL_SM, SIZE_CONTROL_SM, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
        hl.addWidget(icon_lbl)
        title = QLabel("Models & Plugins")
        tf = QFont()
        safe_set_point_size(tf, FONT_SIZE_LARGE)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(f"color: {_TEXT_PRI}; background: transparent; border: none; padding: 0;")
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(header_w)

        tab_bar = QWidget()
        tab_bar.setFixedHeight(SIZE_CONTROL_LG)
        tab_bar.setStyleSheet(toolbar_style(bg=_BG_SURFACE, border=_BORDER_DIM))
        tb = QHBoxLayout(tab_bar)
        tb.setContentsMargins(SPACE_LG, 0, SPACE_LG, 0)
        tb.setSpacing(0)

        self._tab_btns: dict[str, QPushButton] = {}
        for key, label in [("face", "Face Recognition"), ("object", "Object Detection")]:
            btn = QPushButton(label)
            btn.setStyleSheet(_M_TAB_BTN)
            btn.clicked.connect(lambda _c, k=key: self._switch_tab(k))
            tb.addWidget(btn)
            self._tab_btns[key] = btn
        tb.addStretch()
        root.addWidget(tab_bar)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {_BG_BASE};")
        self._stack.addWidget(self._build_face_tab())
        self._stack.addWidget(self._build_object_tab())
        root.addWidget(self._stack, stretch=1)

        self._switch_tab("face")

    def _switch_tab(self, key: str) -> None:
        self._stack.setCurrentIndex(0 if key == "face" else 1)
        for k, btn in self._tab_btns.items():
            btn.setStyleSheet(_M_TAB_BTN_ACTIVE if k == key else _M_TAB_BTN)

    def _build_face_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_BG_BASE};")
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setStyleSheet(f"background: {_BG_BASE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(SPACE_20, SPACE_LG, SPACE_20, SPACE_20)
        bl.setSpacing(SPACE_MD)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        card = QWidget()
        card.setStyleSheet(f"background: {_BG_RAISED}; border-radius: {RADIUS_LG}px;")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cl_outer = QVBoxLayout(card)
        cl_outer.setContentsMargins(0, 0, 0, 0)
        cl_outer.setSpacing(0)

        card_hdr = QWidget()
        card_hdr.setFixedHeight(SIZE_CONTROL_LG)
        card_hdr.setStyleSheet("background: transparent;")
        card_hdr_l = QHBoxLayout(card_hdr)
        card_hdr_l.setContentsMargins(SPACE_20, 0, SPACE_20, 0)
        hdr_lbl = QLabel("FACE RECOGNITION MODEL")
        hdr_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY}; letter-spacing: {SPACE_XXXS}px;"
        )
        card_hdr_l.addWidget(hdr_lbl)
        card_hdr_l.addStretch()
        cl_outer.addWidget(card_hdr)

        cl = QVBoxLayout()
        cl.setContentsMargins(SPACE_20, SPACE_LG, SPACE_20, SPACE_20)
        cl.setSpacing(SPACE_LG)
        cl_outer.addLayout(cl)

        st_row = QHBoxLayout()
        st_row.setSpacing(SPACE_SM)
        self._fm_status_dot = QLabel("●")
        self._fm_status_dot.setFixedSize(SIZE_CONTROL_22, SIZE_CONTROL_22)
        self._fm_status_dot.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_LARGE}px;")
        st_row.addWidget(self._fm_status_dot)
        self._fm_model_status = QLabel("Checking…")
        self._fm_model_status.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
        st_row.addWidget(self._fm_model_status, stretch=1)
        cl.addLayout(st_row)

        self._fm_buffalo_combo = QComboBox()
        self._fm_buffalo_combo.setFixedHeight(SIZE_CONTROL_MD)
        from backend.models.face_model import AVAILABLE_MODELS

        for key, desc in AVAILABLE_MODELS.items():
            self._fm_buffalo_combo.addItem(desc, key)
        self._fm_buffalo_combo.setToolTip(
            "buffalo_l: most accurate, ~300 MB download on first use\n"
            "buffalo_s / buffalo_sc: faster, smaller, less accurate\n"
            "antelopev2: highest accuracy, largest model"
        )
        self._fm_buffalo_combo.activated.connect(self._fm_on_model_changed)
        cl.addLayout(_field_row("Model Pack", self._fm_buffalo_combo))

        path_row = QHBoxLayout()
        path_row.setSpacing(SPACE_MD)
        path_lbl = QLabel("Model Root")
        path_lbl.setFixedWidth(SIZE_FIELD_W)
        path_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_LABEL}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
        path_row.addWidget(path_lbl)
        self._fm_model_path = QLineEdit()
        self._fm_model_path.setPlaceholderText("~/.insightface  (leave blank for default)")
        self._fm_model_path.setFixedHeight(SIZE_CONTROL_MD)
        _fm_folder_action = self._fm_model_path.addAction(
            QIcon("frontend/assets/icons/folder.png"),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        _fm_folder_action.triggered.connect(self._fm_browse_path)
        path_row.addWidget(self._fm_model_path, stretch=1)
        cl.addLayout(path_row)

        act_row = QHBoxLayout()
        act_row.addStretch()
        self._fm_save_reload_btn = QPushButton("Save")
        self._fm_save_reload_btn.setFixedHeight(SIZE_CONTROL_MD)
        self._fm_save_reload_btn.setFixedWidth(SIZE_FIELD_W_SM)
        self._fm_save_reload_btn.setStyleSheet(_PRIMARY_BTN)
        self._fm_save_reload_btn.clicked.connect(self._fm_save_and_reload)
        act_row.addWidget(self._fm_save_reload_btn)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{_SUCCESS};font-weight:{FONT_WEIGHT_BOLD};font-size:{FONT_SIZE_LABEL}px;")
        self._status_lbl.setContentsMargins(0, 0, 0, 0)
        self._status_lbl.setVisible(False)
        act_row.addWidget(self._status_lbl)
        cl.addLayout(act_row)

        submodels_card = QWidget()
        submodels_card.setStyleSheet(f"background: {_BG_RAISED}; border-radius: {RADIUS_LG}px;")
        submodels_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sm_outer = QVBoxLayout(submodels_card)
        sm_outer.setContentsMargins(0, 0, 0, 0)
        sm_outer.setSpacing(0)

        sm_hdr = QWidget()
        sm_hdr.setFixedHeight(SIZE_CONTROL_LG)
        sm_hdr.setStyleSheet("background: transparent;")
        sm_hdr_l = QHBoxLayout(sm_hdr)
        sm_hdr_l.setContentsMargins(SPACE_20, 0, SPACE_20, 0)
        sm_hdr_lbl = QLabel("SUB-MODELS")
        sm_hdr_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY}; letter-spacing: {SPACE_XXXS}px;"
        )
        sm_hdr_l.addWidget(sm_hdr_lbl)
        sm_hdr_l.addStretch()
        sm_outer.addWidget(sm_hdr)

        self._fm_submodels_card = QWidget()
        self._fm_submodels_card.setStyleSheet("background: transparent;")
        self._fm_submodels_vbox = QVBoxLayout(self._fm_submodels_card)
        self._fm_submodels_vbox.setContentsMargins(SPACE_20, SPACE_MD, SPACE_20, SPACE_LG)
        self._fm_submodels_vbox.setSpacing(SPACE_XS)

        _placeholder = QLabel("Load the model first to see sub-modules.")
        _placeholder.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_LABEL}px; font-style: italic;")
        self._fm_submodels_vbox.addWidget(_placeholder)
        sm_outer.addWidget(self._fm_submodels_card)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(SPACE_LG)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        splitter.setOpaqueResize(True)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(card)
        splitter.addWidget(submodels_card)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        _qs = QSettings("SmartEye", "ModelsFace")
        _saved = _qs.value("splitter/sizes")
        if _saved and len(_saved) == 2:
            try:
                splitter.setSizes([int(_saved[0]), int(_saved[1])])
            except (ValueError, TypeError):
                splitter.setSizes([320, 220])
        else:
            splitter.setSizes([320, 220])
        splitter.splitterMoved.connect(lambda _pos, _idx: _qs.setValue("splitter/sizes", splitter.sizes()))
        bl.addWidget(splitter, stretch=1)
        return w

    def _build_object_tab(self) -> QWidget:
        from backend.models.onnx_object_model import ONNXObjectModel

        self._ONNXObjectModel = ONNXObjectModel

        w = QWidget()
        w.setStyleSheet(f"background: {_BG_BASE};")
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setStyleSheet(f"background: {_BG_BASE};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(SPACE_20, SPACE_LG, SPACE_20, SPACE_20)
        bl.setSpacing(SPACE_MD)
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        plugins_card = QWidget()
        plugins_card.setStyleSheet(f"background: {_BG_RAISED}; border-radius: {RADIUS_LG}px;")
        plugins_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        pc_outer = QVBoxLayout(plugins_card)
        pc_outer.setContentsMargins(0, 0, 0, 0)
        pc_outer.setSpacing(0)

        pc_hdr = QWidget()
        pc_hdr.setFixedHeight(SIZE_CONTROL_LG)
        pc_hdr.setStyleSheet("background: transparent;")
        pc_hdr_l = QHBoxLayout(pc_hdr)
        pc_hdr_l.setContentsMargins(SPACE_20, 0, SPACE_20, 0)
        pc_hdr_lbl = QLabel("REGISTERED PLUGINS")
        pc_hdr_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY}; letter-spacing: {SPACE_XXXS}px;"
        )
        pc_hdr_l.addWidget(pc_hdr_lbl)
        pc_hdr_l.addStretch()
        pc_outer.addWidget(pc_hdr)

        self._plugins_container = QWidget()
        self._plugins_container.setStyleSheet("background: transparent;")
        self._plugins_vbox = QVBoxLayout(self._plugins_container)
        self._plugins_vbox.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        self._plugins_vbox.setSpacing(SPACE_6)
        self._plugins_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        pc_outer.addWidget(self._plugins_container)

        add_card = QWidget()
        add_card.setStyleSheet(f"background: {_BG_RAISED}; border-radius: {RADIUS_LG}px;")
        add_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ac_outer = QVBoxLayout(add_card)
        ac_outer.setContentsMargins(0, 0, 0, 0)
        ac_outer.setSpacing(0)

        ac_hdr = QWidget()
        ac_hdr.setFixedHeight(SIZE_CONTROL_LG)
        ac_hdr.setStyleSheet("background: transparent;")
        ac_hdr_l = QHBoxLayout(ac_hdr)
        ac_hdr_l.setContentsMargins(SPACE_20, 0, SPACE_20, 0)
        ac_hdr_lbl = QLabel("REGISTER NEW PLUGIN")
        ac_hdr_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY}; letter-spacing: {SPACE_XXXS}px;"
        )
        ac_hdr_l.addWidget(ac_hdr_lbl)
        ac_hdr_l.addStretch()
        ac_outer.addWidget(ac_hdr)

        ac = QVBoxLayout()
        ac.setContentsMargins(SPACE_20, SPACE_LG, SPACE_20, SPACE_20)
        ac.setSpacing(SPACE_LG)
        ac_outer.addLayout(ac)

        self._ap_name = QLineEdit()
        self._ap_name.setPlaceholderText("Unique plugin name")
        self._ap_name.setFixedHeight(SIZE_CONTROL_MD)
        ac.addLayout(_field_row("Name *", self._ap_name))
        _sep = QFrame()
        _sep.setFixedHeight(SPACE_XXXS)
        _sep.setStyleSheet(f"background: {_BORDER_DIM}; border: none;")
        ac.addWidget(_sep)

        weights_row = QHBoxLayout()
        weights_row.setSpacing(SPACE_MD)
        w_lbl = QLabel("Weights *")
        w_lbl.setFixedWidth(SIZE_FIELD_W)
        w_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_LABEL}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
        weights_row.addWidget(w_lbl)
        self._ap_weight = QLineEdit()
        self._ap_weight.setPlaceholderText(".onnx / .pt / .pth file path")
        self._ap_weight.setFixedHeight(SIZE_CONTROL_MD)
        _folder_action = self._ap_weight.addAction(
            QIcon("frontend/assets/icons/folder.png"),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        _folder_action.triggered.connect(self._ap_browse)
        weights_row.addWidget(self._ap_weight, stretch=1)
        ac.addLayout(weights_row)
        _sep = QFrame()
        _sep.setFixedHeight(SPACE_XXXS)
        _sep.setStyleSheet(f"background: {_BORDER_DIM}; border: none;")
        ac.addWidget(_sep)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(SPACE_LG)
        t_lbl = QLabel("Type")
        t_lbl.setFixedWidth(SIZE_FIELD_W)
        t_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_LABEL}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
        opts_row.addWidget(t_lbl)
        self._ap_type = QComboBox()
        self._ap_type.addItems(["onnx"])
        self._ap_type.setFixedWidth(SIZE_BTN_W_LG)
        self._ap_type.setFixedHeight(SIZE_CONTROL_MD)
        opts_row.addWidget(self._ap_type)

        opts_row.addSpacing(SPACE_XL)
        c_lbl = QLabel("Confidence")
        c_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_LABEL}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
        opts_row.addWidget(c_lbl)
        self._ap_conf = QSpinBox()
        self._ap_conf.setRange(1, 100)
        self._ap_conf.setValue(50)
        self._ap_conf.setSuffix("%")
        self._ap_conf.setFixedWidth(SIZE_BTN_W_100)
        self._ap_conf.setFixedHeight(SIZE_CONTROL_MD)
        opts_row.addWidget(self._ap_conf)

        opts_row.addSpacing(SPACE_XL)
        self._ap_autoassign = QCheckBox("Auto-assign to all cameras")
        self._ap_autoassign.setChecked(True)
        opts_row.addWidget(self._ap_autoassign)
        opts_row.addStretch()
        ac.addLayout(opts_row)
        _sep = QFrame()
        _sep.setFixedHeight(SPACE_XXXS)
        _sep.setStyleSheet(f"background: {_BORDER_DIM}; border: none;")
        ac.addWidget(_sep)

        self._ap_classes_lbl = QLabel("")
        self._ap_classes_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px;")
        self._ap_classes_lbl.setWordWrap(True)
        ac.addWidget(self._ap_classes_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        add_btn = QPushButton("Register Plugin")
        add_btn.setFixedHeight(SIZE_CONTROL_MD)
        add_btn.setFixedWidth(SIZE_BTN_W_160)
        add_btn.setStyleSheet(_PRIMARY_BTN)
        add_btn.clicked.connect(self._do_add_plugin)
        btn_row.addWidget(add_btn)
        ac.addLayout(btn_row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(SPACE_LG)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
        splitter.setOpaqueResize(True)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        splitter.addWidget(plugins_card)
        splitter.addWidget(add_card)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        _qs = QSettings("SmartEye", "ModelsObject")
        _saved = _qs.value("splitter/sizes")
        if _saved and len(_saved) == 2:
            try:
                splitter.setSizes([int(_saved[0]), int(_saved[1])])
            except (ValueError, TypeError):
                splitter.setSizes([320, 260])
        else:
            splitter.setSizes([320, 260])
        splitter.splitterMoved.connect(lambda _pos, _idx: _qs.setValue("splitter/sizes", splitter.sizes()))
        bl.addWidget(splitter, stretch=1)
        return w

    def _fm_load_model_status(self) -> None:
        from backend.models.model_loader import get_face_model

        fm = get_face_model()
        if fm.is_loaded:
            providers_str = ", ".join(p.replace("ExecutionProvider", "") for p in (fm.providers_used or [])) or "CPU"
            self._fm_status_dot.setStyleSheet(f"color: {_SUCCESS}; font-size: {FONT_SIZE_LARGE}px;")
            self._fm_model_status.setText(f"{fm.model_name} — {providers_str}")
            self._fm_model_status.setStyleSheet(f"color: {_SUCCESS}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
        else:
            self._fm_status_dot.setStyleSheet(f"color: {_DANGER}; font-size: {FONT_SIZE_LARGE}px;")
            self._fm_model_status.setText("Not loaded")
            self._fm_model_status.setStyleSheet(f"color: {_DANGER}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_SEMIBOLD};")
        with contextlib.suppress(Exception):
            self._fm_model_path.setText(db.get_setting("insightface_model_dir", ""))
        with contextlib.suppress(Exception):
            saved = db.get_setting("insightface_model_name", "buffalo_l")
            self._fm_buffalo_combo.blockSignals(True)
            for i in range(self._fm_buffalo_combo.count()):
                if self._fm_buffalo_combo.itemData(i) == saved:
                    self._fm_buffalo_combo.setCurrentIndex(i)
                    break
            self._fm_buffalo_combo.blockSignals(False)

    def _refresh_submodels(self) -> None:
        def _drain_layout(lay):
            while lay.count():
                it = lay.takeAt(0)
                w = it.widget()
                if w is not None:
                    try:
                        w.deleteLater()
                    except Exception:
                        pass
                else:
                    sublay = it.layout()
                    if sublay is not None:
                        _drain_layout(sublay)

        _drain_layout(self._fm_submodels_vbox)

        while self._fm_submodels_vbox.count():
            try:
                it = self._fm_submodels_vbox.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.deleteLater()
            except Exception:
                break

        from backend.models.model_loader import get_face_model

        fm = get_face_model()
        submodels = fm.get_submodel_status()

        if not submodels:
            placeholder = QLabel(
                "Load the model first to see sub-modules." if not fm.is_loaded else "No ONNX files found in model directory."
            )
            placeholder.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_LABEL}px; font-style: italic;")
            self._fm_submodels_vbox.addWidget(placeholder)
            return

        hdr = QHBoxLayout()
        for text, stretch in [("File", 1), ("Task", 0), ("Status", 0), ("Enabled", 0)]:
            lbl = QLabel(text.upper())
            lbl.setStyleSheet(
                f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY}; letter-spacing: {SPACE_XXXS}px;"
            )
            if not stretch:
                lbl.setFixedWidth(SIZE_BTN_W_SM)
            hdr.addWidget(lbl, stretch=stretch)
        self._fm_submodels_vbox.addLayout(hdr)

        for i, sm in enumerate(submodels):
            row_w = QWidget()
            row_w.setFixedHeight(SIZE_ROW_MD)
            row_w.setStyleSheet("background: transparent;")
            row_wrap = QVBoxLayout(row_w)
            row_wrap.setContentsMargins(0, 0, 0, 0)
            row_wrap.setSpacing(0)

            row_inner = QWidget()
            row_inner.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_inner)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(SPACE_MD)

            file_lbl = QLabel(sm["filename"])
            file_lbl.setStyleSheet(
                f"color: {_TEXT_PRI}; font-size: {FONT_SIZE_LABEL}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
                " font-family: 'Consolas', monospace;"
            )
            rl.addWidget(file_lbl, stretch=1)

            task_lbl = QLabel(sm["task"].replace("_", " ").title())
            task_lbl.setFixedWidth(SIZE_BTN_W_SM)
            task_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_LABEL}px;")
            rl.addWidget(task_lbl)

            status_dot = QLabel("●")
            status_dot.setFixedWidth(SIZE_BTN_W_SM)
            status_dot.setStyleSheet(f"color: {_SUCCESS if sm['loaded'] else _TEXT_MUTED}; font-size: {FONT_SIZE_SUBHEAD}px;")
            status_dot.setToolTip("Loaded" if sm["loaded"] else "Not loaded / disabled")
            rl.addWidget(status_dot)

            toggle = ToggleSwitch(active_color=_ACCENT)
            toggle.setChecked(sm["enabled"])
            toggle.setFixedWidth(SIZE_BTN_W_SM)
            if sm["required"]:
                toggle.setEnabled(False)
                toggle.setToolTip("Required — cannot be disabled")
            else:
                toggle.setToolTip("Toggle to enable/disable this sub-module (requires model reload)")
                _task = sm["task"]
                toggle.toggled.connect(lambda checked, t=_task: self._on_submodel_toggled(t, checked))
            rl.addWidget(toggle)
            row_wrap.addWidget(row_inner)
            if i < len(submodels) - 1:
                line = QFrame()
                line.setFixedHeight(SPACE_XXXS)
                line.setStyleSheet(f"background: {_BORDER_DIM}; border: none;")
                row_wrap.addWidget(line)
            self._fm_submodels_vbox.addWidget(row_w)

    def _on_submodel_toggled(self, task: str, enabled: bool) -> None:
        from backend.models.face_model import get_allowed_modules, set_allowed_modules

        mods = get_allowed_modules()
        if enabled and task not in mods:
            mods.append(task)
        elif not enabled and task in mods:
            mods.remove(task)
        set_allowed_modules(mods)

    def _fm_on_model_changed(self, idx: int) -> None:
        sel = self._fm_buffalo_combo.itemData(idx) or "buffalo_l"
        db.set_setting("insightface_model_name", sel)
        self._fm_status_dot.setStyleSheet(f"color: {_WARNING_ORANGE}; font-size: {FONT_SIZE_LARGE}px;")
        self._fm_model_status.setText(f"Switching to {sel}…")
        self._fm_model_status.setStyleSheet(
            f"color: {_WARNING_ORANGE}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
        )
        if self._fm_reload_timer:
            self._fm_reload_timer.stop()
        self._fm_reload_timer = QTimer(self)
        self._fm_reload_timer.setSingleShot(True)
        self._fm_reload_timer.timeout.connect(self._fm_force_reload)
        self._fm_reload_timer.start(300)

    def _fm_save_only(self) -> None:
        db.set_setting("insightface_model_dir", self._fm_model_path.text().strip())
        db.set_setting("insightface_model_name", self._fm_buffalo_combo.currentData() or "buffalo_l")
        if db.get_bool("ui_show_save_popups", False):
            QMessageBox.information(self, "Saved", "Model settings saved.")
        else:
            self._flash_status("Saved")

    def _fm_save_and_reload(self) -> None:
        db.set_setting("insightface_model_dir", self._fm_model_path.text().strip())
        db.set_setting("insightface_model_name", self._fm_buffalo_combo.currentData() or "buffalo_l")
        self._fm_force_reload()

    def _fm_force_reload(self) -> None:
        db.set_setting("insightface_model_dir", self._fm_model_path.text().strip())
        db.set_setting("insightface_model_name", self._fm_buffalo_combo.currentData() or "buffalo_l")
        self._fm_reload_model(force=True)

    def _fm_browse_path(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select InsightFace Model Root Folder", self._fm_model_path.text() or ".")
        if folder:
            self._fm_model_path.setText(folder)

    def _fm_reload_model(self, force: bool = False) -> None:
        if self._fm_reload_busy:
            return
        self._fm_reload_busy = True
        old = self._fm_load_worker
        if old is not None and old.isRunning():
            old.quit()
            old.wait(800)
        path = self._fm_model_path.text().strip()
        self._fm_status_dot.setStyleSheet(f"color: {_WARNING_ORANGE}; font-size: {FONT_SIZE_LARGE}px;")
        self._fm_model_status.setText("⏳ Loading model — please wait…")
        self._fm_model_status.setStyleSheet(
            f"color: {_WARNING_ORANGE}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
        )
        self._fm_save_reload_btn.setEnabled(False)
        self._fm_save_reload_btn.setText("Loading…")

        from PySide6.QtCore import QThread, Signal as _Sig

        class _Worker(QThread):
            finished = _Sig(bool, str)

            def __init__(self, p: str, fr: bool, parent=None):
                super().__init__(parent)
                self._p, self._fr = p, fr

            def run(self):
                try:
                    from backend.models.model_loader import get_face_model

                    fm = get_face_model()
                    if self._fr:
                        fm.reload(self._p)
                    else:
                        fm.load(self._p)
                    self.finished.emit(fm.is_loaded, "")
                except Exception as exc:
                    self.finished.emit(False, str(exc))

        worker = _Worker(path, force, self)
        self._fm_load_worker = worker
        if self._fm_progress:
            with contextlib.suppress(Exception):
                self._fm_progress.close()
        self._fm_progress = QProgressDialog("Loading InsightFace model…", None, 0, 0, self)
        self._fm_progress.setWindowTitle("Loading")
        self._fm_progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._fm_progress.setCancelButton(None)
        self._fm_progress.setMinimumDuration(0)
        self._fm_progress.show()

        def _on_done(ok: bool, err: str) -> None:
            self._fm_reload_busy = False
            self._fm_load_worker = None
            with contextlib.suppress(Exception):
                self._fm_progress.close()
                self._fm_progress = None
            self._fm_save_reload_btn.setEnabled(True)
            self._fm_save_reload_btn.setText("Save & Reload Model")
            if ok:
                from backend.models.model_loader import get_face_model

                fm = get_face_model()
                providers_str = ", ".join(p.replace("ExecutionProvider", "") for p in (fm.providers_used or [])) or "CPU"
                note = getattr(fm, "last_load_error", None)
                label = f"{fm.model_name} — {providers_str}"
                if note:
                    label += f"  (note: {note})"
                self._fm_status_dot.setStyleSheet(f"color: {_SUCCESS}; font-size: {FONT_SIZE_LARGE}px;")
                self._fm_model_status.setText(label)
                self._fm_model_status.setStyleSheet(
                    f"color: {_SUCCESS}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
                )
                self._refresh_submodels()
            else:
                msg = f"Error — {err}" if err else "Not loaded"
                self._fm_status_dot.setStyleSheet(f"color: {_DANGER}; font-size: {FONT_SIZE_LARGE}px;")
                self._fm_model_status.setText(msg)
                self._fm_model_status.setStyleSheet(
                    f"color: {_DANGER}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_SEMIBOLD};"
                )

        worker.finished.connect(_on_done)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _refresh_plugin_list(self) -> None:
        while self._plugins_vbox.count():
            item = self._plugins_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        try:
            plugins = db.get_plugins()
        except Exception:
            plugins = []
        if not plugins:
            empty = QLabel("No plugins registered yet.")
            empty.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_LABEL}px; font-style: italic; padding: {SPACE_6}px 0;")
            self._plugins_vbox.addWidget(empty)
            return
        for i, p in enumerate(plugins):
            row_w = QFrame()
            row_w.setStyleSheet(f"QFrame {{ background: {_BG_RAISED}; border: none; border-radius: {RADIUS_MD}px; }}")
            row_w.setFixedHeight(SIZE_ROW_48)
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(SPACE_LG, 0, SPACE_10, 0)
            rl.setSpacing(SPACE_10)
            name_lbl = QLabel(p.get("name", "?"))
            name_lbl.setStyleSheet(
                f"color: {_TEXT_PRI}; font-size: {FONT_SIZE_BODY}px; font-weight: {FONT_WEIGHT_BOLD}; background: transparent;"
            )
            rl.addWidget(name_lbl, stretch=1)
            weight_lbl = QLabel(os.path.basename(p.get("weights_path", "") or ""))
            weight_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; background: transparent;")
            rl.addWidget(weight_lbl)
            type_lbl = QLabel((p.get("model_type") or "").upper())
            type_lbl.setStyleSheet(
                f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_BOLD}; background: transparent;"
            )
            rl.addWidget(type_lbl)
            conf_raw = p.get("confidence", 0) or 0
            conf_pct = int(conf_raw * 100) if conf_raw <= 1.0 else int(conf_raw)
            conf_lbl = QLabel(f"{conf_pct}% conf")
            conf_lbl.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_CAPTION}px; background: transparent;")
            rl.addWidget(conf_lbl)
            del_btn = QPushButton("Delete")
            del_btn.setFixedHeight(SIZE_ITEM_SM)
            del_btn.setFixedWidth(SIZE_BTN_W_72)
            del_btn.setStyleSheet(_RED_TXT_BTN)
            pid, pname = p["id"], p.get("name", "")
            del_btn.clicked.connect(lambda _c, _pid=pid, _pname=pname: self._do_delete_plugin(_pid, _pname))
            rl.addWidget(del_btn)
            self._plugins_vbox.addWidget(row_w)
            sep = QFrame()
            sep.setFixedHeight(SPACE_XXXS)
            sep.setStyleSheet(f"background: {_BORDER_DIM}; border: none;")
            self._plugins_vbox.addWidget(sep)

            try:
                classes = db.get_plugin_classes(plugin_id=pid)
            except Exception:
                classes = []
            if classes:
                from PySide6.QtWidgets import QColorDialog

                cls_header = QLabel("Bbox Colors")
                cls_header.setStyleSheet(
                    f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY};"
                    f" letter-spacing: {SPACE_XXXS}px; padding: {SPACE_XXS}px 0 {SPACE_XXS}px {SPACE_LG}px; background: transparent;"
                )
                self._plugins_vbox.addWidget(cls_header)
                for cls in classes:
                    cls_row = QFrame()
                    cls_row.setStyleSheet(
                        f"QFrame {{ background: {_BG_SURFACE}; border: none; border-radius: {RADIUS_6}px; margin-left: {SPACE_LG}px; }}"
                    )
                    cls_row.setFixedHeight(SIZE_CONTROL_MD)
                    crl = QHBoxLayout(cls_row)
                    crl.setContentsMargins(SPACE_10, 0, SPACE_10, 0)
                    crl.setSpacing(SPACE_SM)

                    color_val = cls.get("color") or ""
                    swatch = QPushButton()
                    swatch.setFixedSize(SIZE_CONTROL_22, SIZE_CONTROL_22)
                    swatch.setToolTip("Click to change bbox color")
                    _c = color_val if color_val else _default_class_color(cls["class_name"])
                    swatch.setStyleSheet(f"background: {_c}; border: {SPACE_XXXS}px solid {_BORDER}; border-radius: {RADIUS_SM}px;")
                    _cid = cls["id"]
                    _cnm = cls["class_name"]

                    def _pick(_, cid=_cid, cnm=_cnm, sw=swatch):
                        color = QColorDialog.getColor(parent=self)
                        if color.isValid():
                            hex_c = color.name()
                            db.set_class_color(cid, hex_c)
                            sw.setStyleSheet(f"background: {hex_c}; border: {SPACE_XXXS}px solid {_BORDER}; border-radius: {RADIUS_SM}px;")
                            notify_plugins_changed()

                    swatch.clicked.connect(_pick)
                    crl.addWidget(swatch)

                    name_lbl = QLabel(cls["class_name"])
                    name_lbl.setStyleSheet(f"color: {_TEXT_PRI}; font-size: {FONT_SIZE_LABEL}px; background: transparent;")
                    crl.addWidget(name_lbl, stretch=1)

                    reset_btn = QPushButton("Reset")
                    reset_btn.setFixedHeight(SIZE_PILL_H)
                    reset_btn.setFixedWidth(SIZE_BTN_W_55)
                    reset_btn.setStyleSheet(_RED_TXT_BTN)

                    def _reset(_, cid=_cid, cnm=_cnm, sw=swatch):
                        db.set_class_color(cid, "")
                        sw.setStyleSheet(
                            f"background: {_default_class_color(cnm)};"
                            f" border: {SPACE_XXXS}px solid {_BORDER}; border-radius: {RADIUS_SM}px;"
                        )
                        notify_plugins_changed()

                    reset_btn.clicked.connect(_reset)
                    crl.addWidget(reset_btn)
                    self._plugins_vbox.addWidget(cls_row)

            spacer = QFrame()
            spacer.setFixedHeight(SPACE_6)
            spacer.setStyleSheet("background: transparent; border: none;")
            self._plugins_vbox.addWidget(spacer)

    def _do_delete_plugin(self, plugin_id: int, plugin_name: str) -> None:
        resp = QMessageBox.question(
            self,
            "Delete Plugin",
            f"Delete plugin '{plugin_name}'?\n\nThis will remove it from all cameras permanently.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            db.delete_plugin(plugin_id)
        except Exception as exc:
            logger.exception("Failed to delete plugin %s", plugin_id)
            QMessageBox.critical(self, "Error", f"Failed to delete plugin:\n{exc}")
            return
        mgr = get_manager()
        if mgr:
            mgr.invalidate_camera_cache()
            mgr.reload()
            notify_plugins_changed()
        self._refresh_plugin_list()

    def _ap_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Model Weights", "", "Model Files (*.onnx *.pt *.pth);;All Files (*)")
        if not path:
            return
        self._ap_weight.setText(path)
        self._ap_extracted_classes.clear()
        self._ap_classes_lbl.setText("Inspecting model…")
        try:
            ext = os.path.splitext(path)[1].lower()
            names = self._ONNXObjectModel.inspect_model(path) if ext == ".onnx" else self._ObjectModel.inspect_model(path)
            if names:
                if isinstance(names, dict):
                    class_map = names.get("class_names") or names.get("classes") or {}
                    class_list = [class_map[k] for k in sorted(class_map.keys())]
                else:
                    class_list = list(names)
                self._ap_extracted_classes.extend(class_list)
                self._ap_classes_lbl.setText(
                    f"Found {len(class_list)} classes: " + ", ".join(class_list[:6]) + ("…" if len(class_list) > 6 else "")
                )
            else:
                self._ap_classes_lbl.setText("No classes detected — you can add them manually later.")
        except Exception as exc:
            self._ap_classes_lbl.setText(f"Inspect failed: {exc}")

    def _do_add_plugin(self) -> None:
        name = self._ap_name.text().strip()
        weight = self._ap_weight.text().strip()
        if not name or not weight:
            QMessageBox.warning(self, "Required Fields", "Name and Weights path are required.")
            return
        mtype = self._ap_type.currentText()
        conf = self._ap_conf.value() / 100.0
        try:
            plugin_id = db.add_plugin(name, mtype, weight, conf)
            for idx, cls_name in enumerate(self._ap_extracted_classes):
                db.add_plugin_class(plugin_id, idx, cls_name, cls_name)
            if self._ap_autoassign.isChecked():
                for cam in db.get_cameras():
                    db.assign_plugin_to_camera(cam["id"], plugin_id)
            mgr = get_manager()
            if mgr:
                mgr.invalidate_camera_cache()
                mgr.reload()
                notify_plugins_changed()
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self,
                "Name Already Exists",
                f"A plugin named '{name}' already exists.\nChoose a different name or delete the existing plugin first.",
            )
            return
        except Exception as exc:
            logger.exception("Failed to add plugin")
            QMessageBox.critical(self, "Error", f"Failed:\n{exc}")
            return
        self._ap_name.clear()
        self._ap_weight.clear()
        self._ap_conf.setValue(50)
        self._ap_classes_lbl.setText("")
        self._ap_extracted_classes.clear()
        self._refresh_plugin_list()
        if db.get_bool("ui_show_save_popups", False):
            QMessageBox.information(self, "Registered", f"Plugin '{name}' registered successfully.")
        else:
            self._flash_status("Saved")

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

    def on_activated(self) -> None:
        self._fm_load_model_status()
        self._refresh_plugin_list()
        self._refresh_submodels()

    def on_deactivated(self) -> None:
        if self._fm_reload_timer:
            self._fm_reload_timer.stop()

    def on_unload(self) -> None:
        if self._fm_reload_timer:
            self._fm_reload_timer.stop()
