from __future__ import annotations

import logging
import os
import sqlite3
import contextlib
from datetime import datetime

import cv2
from PySide6.QtCore import Qt, QSize, QSettings, QTimer, QEvent, QDate
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QDateEdit,
    QWidget,
)

from backend.camera.playback_thread import PlaybackThread
from backend.repository import db
from frontend.app_theme import page_base_styles, safe_set_point_size
from frontend.icon_theme import themed_icon_pixmap
from frontend.dialogs import apply_popup_theme
from frontend.widgets.toggle_switch import ToggleSwitch
from frontend.widgets.video_widget import VideoWidget


from frontend.styles._colors import (
    _ACCENT,
    _ACCENT_BG_18,
    _ACCENT_HI,
    _ACCENT_HI_BG_07,
    _ACCENT_HI_BG_22,
    _ACCENT_HI_BG_45,
    _BG_BASE,
    _BG_OVERLAY,
    _BG_SURFACE,
    _BLACK,
    _BORDER_DARK,
    _BORDER_DIM,
    _TEXT_MUTED,
    _TEXT_PRI,
    _TEXT_SEC,
)
from frontend.styles._input_styles import _FORM_INPUTS, _FORM_COMBO
from frontend.styles._btn_styles import _PRIMARY_BTN, _SECONDARY_BTN, _ICON_BTN, _ICON_BTN_DANGER
from frontend.styles._calendar_styles import date_popup_styles
from frontend.styles.page_styles import (
    card_shell_style,
    divider_style,
    filter_tool_button_style,
    header_bar_style,
    muted_label_style,
    neutral_badge_style,
    section_kicker_style,
    text_style,
    toolbar_style,
    transparent_surface_style,
)
from frontend.pages.playback._widgets import ClipRowWidget
from frontend.date_utils import day_timestamp_bounds, normalize_date_range, qdate_to_date
from frontend.ui_tokens import (
    FONT_SIZE_CAPTION,
    FONT_SIZE_HEADING,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_WEIGHT_BOLD,
    RADIUS_11,
    RADIUS_3,
    RADIUS_6,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_XS,
    SIZE_CONTROL_LG,
    SIZE_CONTROL_MD,
    SIZE_CONTROL_SM,
    SIZE_DIALOG_W,
    SIZE_FIELD_W_XS,
    SIZE_HEADER_H,
    SIZE_ICON_10,
    SIZE_PILL_H,
    SIZE_ROW_XL,
    SIZE_SECTION_H,
    SPACE_10,
    SPACE_14,
    SPACE_20,
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

_STYLESHEET = (
    page_base_styles()
    + f"""
{date_popup_styles()}
QSlider::groove:horizontal {{
    height: {SPACE_XS}px; background: {_BG_OVERLAY}; border-radius: {RADIUS_XS}px;
}}
QSlider::handle:horizontal {{
    background: {_ACCENT_HI};
    width: {SPACE_14}px; height: {SPACE_14}px;
    margin: -{SPACE_5}px 0;
    border: none;
    border-radius: 999px;
}}
QSlider#timeline_slider::handle:horizontal {{
    background: {_ACCENT_HI};
    width: {SPACE_14}px; height: {SPACE_14}px;
    margin: -{SPACE_5}px 0;
    border: none;
    border-radius: 999px;
    image: none;
}}
QSlider::sub-page:horizontal {{ background: {_ACCENT}; border-radius: {RADIUS_XS}px; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{
    padding: {SPACE_10}px {SPACE_14}px; color: {_TEXT_SEC}; border-radius: {RADIUS_6}px; background: transparent;
}}
QListWidget::item:selected {{ background: {_ACCENT_BG_18}; color: {_TEXT_PRI}; }}
QListWidget::item:hover:!selected {{ background: {_ACCENT_HI_BG_07}; color: {_TEXT_PRI}; }}
QListWidget#clips_list {{ background: {_BG_BASE}; }}
QListWidget#clips_list::item {{ padding: 0; color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; }}
QListWidget#clips_list::item:selected {{ background: transparent; color: {_TEXT_PRI}; }}
QListWidget#clips_list::item:hover:!selected {{ background: transparent; }}
QListWidget#clips_list {{ padding-bottom: {SPACE_SM}px; }}
QPushButton#clip_delete {{
    background: transparent;
    border: none;
    padding: 0;
}}
QPushButton#clip_delete:hover {{
    background: transparent;
}}
QScrollBar:vertical {{ border: none; background: transparent; width: {SPACE_6}px; margin: {SPACE_XXS}px 0; }}
    QScrollBar::handle:vertical {{
        background: {_ACCENT_HI_BG_22}; min-height: {SIZE_CONTROL_SM}px; border-radius: {RADIUS_3}px;
    }}
QScrollBar::handle:vertical:hover {{ background: {_ACCENT_HI_BG_45}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
)

logger = logging.getLogger(__name__)
_PLAYBACK_TITLE_STYLE = text_style(_TEXT_PRI)
_TIME_LABEL_STYLE = text_style(_TEXT_SEC, size=FONT_SIZE_LABEL, extra=f"padding-left: {SPACE_LG}px;")
_BG_BASE_STYLE = f"background: {_BG_BASE};"
_VIDEO_CARD_STYLE = f"background: {_BLACK}; border-radius: {RADIUS_LG}px;"
_SPEED_LABEL_STYLE = text_style(_TEXT_MUTED, size=FONT_SIZE_CAPTION, weight=FONT_WEIGHT_BOLD)


_RETIRED_PLAYBACK_THREADS: list[PlaybackThread] = []


def _icon_btn(icon_path: str, size: int = 36, danger: bool = False) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(size, size)
    btn.setStyleSheet(_ICON_BTN_DANGER if danger else _ICON_BTN)
    pix = QPixmap(icon_path)
    if not pix.isNull():
        btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(int(size * 0.52), int(size * 0.52)))
    return btn


def _set_list_active(list_widget: QListWidget, item: QListWidgetItem, activate_cb) -> None:
    if list_widget and item:
        list_widget.setCurrentItem(item)
    if activate_cb:
        activate_cb(item)


class PlaybackPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_STYLESHEET)
        self._playback_thread: PlaybackThread | None = None
        self._total_frames = 0
        self._current_frame = 0
        self._events: list = []
        self._video_fps = 30.0
        self._saved_clips: list[str] = []
        self._rule_camera_id = -1
        self._user_seeking = False
        self._seek_was_playing = False
        self._seek_pending: int | None = None
        self._seek_timer = QTimer(self)
        self._seek_timer.setInterval(40)
        self._seek_timer.setSingleShot(True)
        self._seek_timer.timeout.connect(self._flush_seek)
        self._clip_cards: list[tuple[QListWidgetItem, ClipRowWidget]] = []
        self._filters_ready = False
        self._clip_filter_camera = None
        self._clip_filter_rule = None
        self._clip_filter_object = None
        self._clip_filter_face = None
        self._clip_filter_from = None
        self._clip_filter_to = None
        self._clip_filters_dialog: QDialog | None = None
        self._filters_btn: QToolButton | None = None
        self._build_ui()
        self._load_rule_cameras()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header_w = QWidget()
        header_w.setFixedHeight(SIZE_HEADER_H)
        header_w.setObjectName("pb_header")
        header_w.setStyleSheet(header_bar_style(widget_id="pb_header", bg=_BG_BASE, border=_BORDER_DIM))
        hl = QHBoxLayout(header_w)
        hl.setContentsMargins(SPACE_XL, 0, SPACE_XL, 0)
        hl.setSpacing(SPACE_10)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(SIZE_CONTROL_SM, SIZE_CONTROL_SM)
        pix = themed_icon_pixmap("frontend/assets/icons/playback.png", SIZE_CONTROL_SM, SIZE_CONTROL_SM)
        if not pix.isNull():
            icon_lbl.setPixmap(pix)
        hl.addWidget(icon_lbl)

        title = QLabel("Playback & Review")
        tf = QFont()
        safe_set_point_size(tf, FONT_SIZE_HEADING)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(_PLAYBACK_TITLE_STYLE)
        hl.addWidget(title)
        hl.addStretch()

        self._fps_label = QLabel("FPS: —")
        self._fps_label.setStyleSheet(muted_label_style(size=FONT_SIZE_LABEL))
        hl.addWidget(self._fps_label)

        self._time_label = QLabel("00:00:00 / 00:00:00")
        self._time_label.setStyleSheet(_TIME_LABEL_STYLE)
        hl.addWidget(self._time_label)
        root.addWidget(header_w)

        toolbar = QWidget()
        toolbar.setFixedHeight(SIZE_HEADER_H)
        toolbar.setStyleSheet(toolbar_style(bg=_BG_SURFACE, border=_BORDER_DIM))
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(SPACE_XL, SPACE_SM, SPACE_XL, SPACE_SM)
        tl.setSpacing(SPACE_MD)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select a video file to begin…")
        self._path_edit.setReadOnly(True)
        self._path_edit.setFixedHeight(SIZE_CONTROL_MD)
        self._path_edit.setStyleSheet(_FORM_INPUTS)
        _folder_act = self._path_edit.addAction(
            QIcon("frontend/assets/icons/folder.png"),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        _folder_act.triggered.connect(self._open_file)
        tl.addWidget(self._path_edit, stretch=1)

        _sep1 = QWidget()
        _sep1.setFixedSize(SPACE_XXXS, SPACE_XL)
        _sep1.setStyleSheet(divider_style(_BORDER_DIM, SPACE_XL))
        tl.addWidget(_sep1)

        det_lbl = QLabel("Detection")
        det_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; font-weight: {FONT_WEIGHT_BOLD}; letter-spacing: 0.{SPACE_XS}px;"
        )
        tl.addWidget(det_lbl)
        self._detect_toggle = ToggleSwitch()
        self._detect_toggle.setToolTip("Enable detection overlay during playback")
        self._detect_toggle.toggled.connect(self._on_detection_toggled)
        tl.addWidget(self._detect_toggle)

        _sep2 = QWidget()
        _sep2.setFixedSize(SPACE_XXXS, SPACE_XL)
        _sep2.setStyleSheet(divider_style(_BORDER_DIM, SPACE_XL))
        tl.addWidget(_sep2)

        rec_lbl = QLabel("Auto-Clip")
        rec_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; font-weight: {FONT_WEIGHT_BOLD}; letter-spacing: 0.{SPACE_XS}px;"
        )
        tl.addWidget(rec_lbl)
        self._record_toggle = ToggleSwitch()
        self._record_toggle.setToolTip("Saves a clip to data/clips/ when a rule fires. Requires Detection ON.")
        self._record_toggle.toggled.connect(self._on_record_toggled)
        tl.addWidget(self._record_toggle)
        self._load_playback_toggle_settings()

        _sep3 = QWidget()
        _sep3.setFixedSize(SPACE_XXXS, SPACE_XL)
        _sep3.setStyleSheet(divider_style(_BORDER_DIM, SPACE_XL))
        tl.addWidget(_sep3)

        rule_lbl = QLabel("Rules")
        rule_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; font-weight: {FONT_WEIGHT_BOLD}; letter-spacing: 0.{SPACE_XS}px;"
        )
        tl.addWidget(rule_lbl)
        self._rule_combo = QComboBox()
        self._rule_combo.setFixedHeight(SIZE_CONTROL_MD)
        self._rule_combo.setFixedWidth(SIZE_DIALOG_W)
        self._rule_combo.setStyleSheet(_FORM_COMBO)
        self._rule_combo.currentIndexChanged.connect(self._on_rule_camera_changed)
        tl.addWidget(self._rule_combo)
        root.addWidget(toolbar)

        content = QWidget()
        content.setStyleSheet(_BG_BASE_STYLE)
        cl = QVBoxLayout(content)
        cl.setContentsMargins(SPACE_20, SPACE_LG, SPACE_20, SPACE_LG)
        cl.setSpacing(SPACE_MD)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(SPACE_SM)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        left = QWidget()
        left.setStyleSheet(transparent_surface_style())
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(SPACE_10)

        self._video_widget = VideoWidget()
        self._video_widget.setMinimumSize(480, 280)
        self._video_widget.setStyleSheet(_VIDEO_CARD_STYLE)
        ll.addWidget(self._video_widget, stretch=1)

        ctrl_card = QWidget()
        ctrl_card.setStyleSheet(card_shell_style())
        cc = QVBoxLayout(ctrl_card)
        cc.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        cc.setSpacing(SPACE_10)

        self._timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self._timeline_slider.setObjectName("timeline_slider")
        self._timeline_slider.setRange(0, 100)
        self._timeline_slider.setValue(0)
        self._timeline_slider.setStyleSheet(
            f"""
QSlider::groove:horizontal {{
    height: {SPACE_XS}px; background: {_BG_OVERLAY}; border-radius: {RADIUS_XS}px;
}}
QSlider::sub-page:horizontal {{
    background: {_ACCENT}; border-radius: {RADIUS_XS}px;
}}
QSlider::handle:horizontal {{
    background: {_ACCENT_HI};
    width: {SPACE_14}px; height: {SPACE_14}px;
    margin: -{SPACE_5}px 0;
    border: none;
    border-radius: {SPACE_14 // 2}px;
    image: none;
}}
"""
        )
        self._timeline_slider.sliderPressed.connect(self._on_seek_pressed)
        self._timeline_slider.sliderMoved.connect(self._on_seek_moved)
        self._timeline_slider.sliderReleased.connect(self._on_seek)
        cc.addWidget(self._timeline_slider)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(SPACE_6)

        self._play_btn = _icon_btn("frontend/assets/icons/play.png", SIZE_SECTION_H)
        self._play_btn.setToolTip("Play / Pause")
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self._play_btn)

        self._stop_btn = _icon_btn("frontend/assets/icons/stop.png", SIZE_SECTION_H, danger=True)
        self._stop_btn.setToolTip("Stop")
        self._stop_btn.clicked.connect(self._stop)
        ctrl_row.addWidget(self._stop_btn)

        _div = QWidget()
        _div.setFixedSize(SPACE_XXXS, SIZE_PILL_H)
        _div.setStyleSheet(divider_style(_BORDER_DIM, SIZE_PILL_H))
        ctrl_row.addSpacing(SPACE_6)
        ctrl_row.addWidget(_div)
        ctrl_row.addSpacing(SPACE_6)

        speed_lbl = QLabel("Speed")
        speed_lbl.setStyleSheet(_SPEED_LABEL_STYLE)
        ctrl_row.addWidget(speed_lbl)

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["0.25×", "0.5×", "1×", "2×", "4×"])
        self._speed_combo.setCurrentIndex(2)
        self._speed_combo.setFixedWidth(SIZE_FIELD_W_XS)
        self._speed_combo.setFixedHeight(SIZE_CONTROL_MD)
        self._speed_combo.setStyleSheet(_FORM_COMBO)
        self._speed_combo.currentIndexChanged.connect(self._change_speed)
        ctrl_row.addWidget(self._speed_combo)

        ctrl_row.addStretch()

        snap_btn = QPushButton("  Snapshot")
        snap_btn.setFixedHeight(SIZE_CONTROL_MD)
        snap_btn.setStyleSheet(_PRIMARY_BTN)
        snap_btn.clicked.connect(self._save_snapshot)
        ctrl_row.addWidget(snap_btn)

        cc.addLayout(ctrl_row)
        ll.addWidget(ctrl_card)
        splitter.addWidget(left)

        right = QWidget()
        right.setMinimumWidth(200)
        right.setMaximumWidth(SIZE_DIALOG_W)
        right.setStyleSheet(transparent_surface_style())
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setHandleWidth(SPACE_SM)
        right_split.setStyleSheet("QSplitter::handle { background: transparent; }")

        events_card = QWidget()
        events_card.setStyleSheet(card_shell_style())
        ec = QVBoxLayout(events_card)
        ec.setContentsMargins(0, 0, 0, SPACE_MD)
        ec.setSpacing(0)

        ev_hdr_w = QWidget()
        ev_hdr_w.setFixedHeight(SIZE_CONTROL_LG)
        ev_hdr_w.setStyleSheet(transparent_surface_style())
        ev_hdr_l = QHBoxLayout(ev_hdr_w)
        ev_hdr_l.setContentsMargins(SPACE_LG, 0, SPACE_MD, 0)
        ev_hdr_l.setSpacing(SPACE_SM)

        ev_title = QLabel("DETECTION EVENTS")
        ev_title.setStyleSheet(section_kicker_style())
        ev_hdr_l.addWidget(ev_title)
        ev_hdr_l.addStretch()

        self._event_badge = QLabel("0")
        self._event_badge.setFixedSize(SIZE_PILL_H, SIZE_PILL_H)
        self._event_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._event_badge.setStyleSheet(neutral_badge_style())
        ev_hdr_l.addWidget(self._event_badge)
        ec.addWidget(ev_hdr_w)

        self._events_list = QListWidget()
        self._events_list.setAlternatingRowColors(False)
        self._events_list.viewport().setAutoFillBackground(False)
        self._events_list.viewport().setStyleSheet("background: transparent;")
        self._events_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._events_list.itemClicked.connect(self._on_event_clicked)
        ec.addWidget(self._events_list, stretch=1)

        right_split.addWidget(events_card)

        clips_card = QWidget()
        clips_card.setStyleSheet(card_shell_style())
        ccv = QVBoxLayout(clips_card)
        ccv.setContentsMargins(0, 0, 0, SPACE_MD)
        ccv.setSpacing(0)

        clips_hdr_w = QWidget()
        clips_hdr_w.setFixedHeight(SIZE_CONTROL_LG)
        clips_hdr_w.setStyleSheet(transparent_surface_style())
        clips_hdr_l = QHBoxLayout(clips_hdr_w)
        clips_hdr_l.setContentsMargins(SPACE_LG, 0, SPACE_MD, 0)
        clips_hdr_l.setSpacing(SPACE_SM)

        clips_title = QLabel("SAVED CLIPS")
        clips_title.setStyleSheet(section_kicker_style())
        clips_hdr_l.addWidget(clips_title)
        clips_hdr_l.addStretch()
        ccv.addWidget(clips_hdr_w)

        self._filters_btn = QToolButton()
        self._filters_btn.setText("Filters")
        _flt = themed_icon_pixmap("frontend/assets/icons/arrow_down.png", SIZE_ICON_10, SIZE_ICON_10)
        self._filters_btn.setIcon(QIcon(_flt) if not _flt.isNull() else QIcon("frontend/assets/icons/arrow_down.png"))
        self._filters_btn.setIconSize(QSize(SIZE_ICON_10, SIZE_ICON_10))
        self._filters_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._filters_btn.setStyleSheet(filter_tool_button_style())
        self._filters_btn.clicked.connect(self._open_clip_filters_dialog)
        clips_hdr_l.addWidget(self._filters_btn)

        self._ensure_clip_filters_dialog()
        self._load_clip_filters()

        self._clips_list = QListWidget()
        self._clips_list.setObjectName("clips_list")
        self._clips_list.setAlternatingRowColors(False)
        self._clips_list.viewport().setAutoFillBackground(False)
        self._clips_list.viewport().setStyleSheet("background: transparent;")
        self._clips_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._clips_list.setSpacing(SPACE_XXS)
        self._clips_list.setUniformItemSizes(True)
        self._clips_list.setViewportMargins(0, 0, 0, SPACE_SM)
        self._clips_list.itemClicked.connect(self._on_clip_item_activated)
        self._clips_list.currentItemChanged.connect(self._sync_clip_card_selection)
        self._clips_list.viewport().installEventFilter(self)
        ccv.addWidget(self._clips_list, stretch=1)
        self._filters_ready = True

        self._clip_status = QLabel("")
        self._clip_status.setStyleSheet(
            f"{muted_label_style(size=FONT_SIZE_MICRO)} padding: 0 {SPACE_LG}px {SPACE_SM}px {SPACE_LG}px;"
        )
        self._clip_status.setWordWrap(True)
        ccv.addWidget(self._clip_status)

        right_split.addWidget(clips_card)

        _qs = QSettings("SmartEye", "Playback")
        _rsaved = _qs.value("splitter/right_sizes")
        if _rsaved and len(_rsaved) == 2:
            try:
                right_split.setSizes([int(_rsaved[0]), int(_rsaved[1])])
            except (ValueError, TypeError):
                right_split.setSizes([650, 420])
        else:
            right_split.setSizes([650, 420])
        right_split.splitterMoved.connect(lambda _pos, _idx: _qs.setValue("splitter/right_sizes", right_split.sizes()))

        rl.addWidget(right_split)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        _qs = QSettings("SmartEye", "Playback")
        _saved = _qs.value("splitter/sizes")
        if _saved and len(_saved) == 2:
            try:
                splitter.setSizes([int(_saved[0]), int(_saved[1])])
            except (ValueError, TypeError):
                splitter.setSizes([900, 300])
        else:
            splitter.setSizes([900, 300])
        splitter.splitterMoved.connect(lambda _pos, _idx: _qs.setValue("splitter/sizes", splitter.sizes()))
        cl.addWidget(splitter, stretch=1)
        root.addWidget(content, stretch=1)

    def on_activated(self) -> None:
        self._refresh_clips_list()

    def on_deactivated(self) -> None:
        self._seek_timer.stop()
        self._stop(wait_ms=1500)

    def on_unload(self) -> None:
        self._seek_timer.stop()
        self._stop(wait_ms=5000)

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            os.path.dirname(self._path_edit.text()) or "",
            "Video Files (*.mp4 *.avi *.mkv *.mov *.wmv)",
        )
        if not path:
            return
        self._start_playback(path)

    def eventFilter(self, obj, event):
        if obj is self._clips_list.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if self._clips_list.itemAt(event.pos()) is None:
                self._clips_list.clearSelection()
                self._sync_clip_card_selection(None, None)
        return super().eventFilter(obj, event)

    def _on_frame(self, camera_id, frame, state) -> None:
        frame_idx = state.get("frame_index", 0)
        self._current_frame = frame_idx
        self._video_widget.update_frame(frame, state)
        if not self._user_seeking:
            self._timeline_slider.blockSignals(True)
            self._timeline_slider.setValue(frame_idx)
            self._timeline_slider.blockSignals(False)
        if self._total_frames > 0:
            cur_sec = frame_idx / self._video_fps
            total_sec = self._total_frames / self._video_fps
            self._time_label.setText(f"{self._format_time(cur_sec)} / {self._format_time(total_sec)}")

    def _on_detection_event(self, camera_id, frame_idx, event_data) -> None:
        self._events.append((frame_idx, event_data))
        rules = event_data.get("triggered_rules") or []
        detections = (event_data or {}).get("detections", {}) or {}
        identity = (event_data or {}).get("identity") or detections.get("identity") or "unknown"
        gender = detections.get("gender") or "unknown"
        base = ", ".join(rules) if rules else f"Frame {frame_idx}"
        desc = f"{base} - {identity} ({str(gender).title()})"
        self._events_list.addItem(QListWidgetItem(f"[{frame_idx}]  {desc}"))
        self._event_badge.setText(str(len(self._events)))

    def _on_clip_saved(self, path: str) -> None:
        self._saved_clips.append(path)
        self._refresh_clips_list()
        self._clip_status.setText(f"Saved: {os.path.basename(path)}")

    def _on_clip_failed(self, message: str) -> None:
        self._clip_status.setText(message)

    def _on_detection_toggled(self, state: bool) -> None:
        try:
            db.set_setting("playback_detection_enabled", bool(state))
        except (sqlite3.Error, OSError, ValueError):
            logger.warning("Failed to persist playback detection setting", exc_info=True)
        if self._playback_thread:
            self._playback_thread.set_detection_enabled(state)

    def _on_record_toggled(self, state: bool) -> None:
        try:
            db.set_setting("playback_record_enabled", bool(state))
        except (sqlite3.Error, OSError, ValueError):
            logger.warning("Failed to persist playback record setting", exc_info=True)
        if self._playback_thread:
            self._playback_thread.set_record_enabled(state)

    def _load_playback_toggle_settings(self) -> None:
        try:
            det = db.get_bool("playback_detection_enabled", False)
            rec = db.get_bool("playback_record_enabled", False)
            self._detect_toggle.setChecked(bool(det))
            self._record_toggle.setChecked(bool(rec))
        except (sqlite3.Error, OSError, ValueError):
            logger.warning("Failed to load playback toggle settings", exc_info=True)
            self._detect_toggle.setChecked(False)
            self._record_toggle.setChecked(False)

    def _on_event_clicked(self, item) -> None:
        idx = self._events_list.row(item)
        if idx < len(self._events):
            frame_idx, _ = self._events[idx]
            if self._playback_thread:
                self._playback_thread.seek(frame_idx)

    def _on_finished(self, camera_id=None) -> None:
        self._sync_play_button(paused=True)

    def _toggle_play(self) -> None:
        if self._playback_thread is None:
            if self._path_edit.text():
                self._start_playback(self._path_edit.text())
            return
        if not self._playback_thread.isRunning():
            if self._path_edit.text():
                self._start_playback(self._path_edit.text())
            return
        if self._playback_thread.is_paused:
            self._playback_thread.resume()
            self._sync_play_button(paused=False)
        else:
            self._playback_thread.pause()
            self._sync_play_button(paused=True)

    def _stop(self, wait_ms: int = 1500) -> None:
        thread = self._playback_thread
        self._playback_thread = None
        if thread:
            self._detach_playback_thread_signals(thread)
            thread.stop()
            if thread.isRunning() and not thread.wait(max(250, int(wait_ms))):
                logger.warning("Playback thread is still running; deferring destruction until finished")
                self._retain_playback_thread_until_finished(thread)
            else:
                thread.deleteLater()
        self._video_widget.show_placeholder("No video loaded")
        self._timeline_slider.setValue(0)
        self._fps_label.setText("FPS: —")
        self._time_label.setText("00:00:00 / 00:00:00")
        self._sync_play_button(paused=True)

    def _detach_playback_thread_signals(self, thread: PlaybackThread) -> None:
        with contextlib.suppress(Exception):
            thread.frame_ready.disconnect(self._on_frame)
        with contextlib.suppress(Exception):
            thread.detection_event.disconnect(self._on_detection_event)
        with contextlib.suppress(Exception):
            thread.playback_finished.disconnect(self._on_finished)
        with contextlib.suppress(Exception):
            thread.clip_saved.disconnect(self._on_clip_saved)
        with contextlib.suppress(Exception):
            thread.clip_failed.disconnect(self._on_clip_failed)

    def _retain_playback_thread_until_finished(self, thread: PlaybackThread) -> None:
        if thread in _RETIRED_PLAYBACK_THREADS:
            return
        _RETIRED_PLAYBACK_THREADS.append(thread)

        def _cleanup() -> None:
            with contextlib.suppress(Exception):
                if thread in _RETIRED_PLAYBACK_THREADS:
                    _RETIRED_PLAYBACK_THREADS.remove(thread)
            with contextlib.suppress(Exception):
                thread.deleteLater()

        with contextlib.suppress(Exception):
            thread.finished.connect(_cleanup)

    def _on_seek_pressed(self) -> None:
        self._user_seeking = True
        self._seek_was_playing = False
        if self._playback_thread and self._playback_thread.isRunning():
            self._seek_was_playing = not self._playback_thread.is_paused
            self._playback_thread.pause()
            self._sync_play_button(paused=True)

    def _on_seek_moved(self, value: int) -> None:
        if self._total_frames > 0:
            cur_sec = value / self._video_fps
            total_sec = self._total_frames / self._video_fps
            self._time_label.setText(f"{self._format_time(cur_sec)} / {self._format_time(total_sec)}")
        self._seek_pending = value
        if not self._seek_timer.isActive():
            self._seek_timer.start()

    def _on_seek(self) -> None:
        if self._playback_thread:
            self._playback_thread.seek(self._timeline_slider.value())
            if self._seek_was_playing:
                self._playback_thread.resume()
                self._sync_play_button(paused=False)
        self._user_seeking = False
        self._seek_was_playing = False
        self._seek_pending = None

    def _flush_seek(self) -> None:
        if self._seek_pending is None:
            return
        if self._playback_thread:
            self._playback_thread.seek(self._seek_pending)

    def _change_speed(self, idx: int) -> None:
        self._apply_speed()

    def _apply_speed(self) -> None:
        speeds = [0.25, 0.5, 1.0, 2.0, 4.0]
        idx = self._speed_combo.currentIndex()
        if self._playback_thread and idx < len(speeds):
            base_fps = self._video_fps or 30.0
            self._playback_thread.set_fps_limit(max(0.25, base_fps * speeds[idx]))

    def _save_snapshot(self) -> None:
        if not hasattr(self._video_widget, "_last_frame") or self._video_widget._last_frame is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Snapshot", "snapshot.jpg", "JPEG (*.jpg);;PNG (*.png)")
        if path:
            cv2.imwrite(path, self._video_widget._last_frame)

    def _ensure_clip_filters_dialog(self) -> None:
        if self._clip_filters_dialog is not None:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Clip Filters")
        apply_popup_theme(dlg)
        dlg.setModal(False)
        dlg.setFixedWidth(700)

        fl = QVBoxLayout(dlg)
        fl.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        fl.setSpacing(SPACE_SM)

        row1 = QHBoxLayout()
        row1.setSpacing(SPACE_SM)
        self._clip_filter_face = QLineEdit()
        self._clip_filter_face.setPlaceholderText("Face label")
        self._clip_filter_face.setFixedHeight(SIZE_CONTROL_MD)
        self._clip_filter_face.setStyleSheet(_FORM_INPUTS)
        row1.addWidget(self._clip_filter_face, stretch=1)

        self._clip_filter_camera = QComboBox()
        self._clip_filter_camera.setFixedHeight(SIZE_CONTROL_MD)
        self._clip_filter_camera.setMinimumWidth(160)
        self._clip_filter_camera.setStyleSheet(_FORM_COMBO)
        row1.addWidget(self._clip_filter_camera)

        self._clip_filter_rule = QComboBox()
        self._clip_filter_rule.setFixedHeight(SIZE_CONTROL_MD)
        self._clip_filter_rule.setMinimumWidth(160)
        self._clip_filter_rule.setStyleSheet(_FORM_COMBO)
        row1.addWidget(self._clip_filter_rule)
        fl.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(SPACE_SM)
        self._clip_filter_object = QComboBox()
        self._clip_filter_object.setFixedHeight(SIZE_CONTROL_MD)
        self._clip_filter_object.setMinimumWidth(160)
        self._clip_filter_object.setStyleSheet(_FORM_COMBO)
        row2.addWidget(self._clip_filter_object)

        self._clip_filter_from = QDateEdit()
        self._clip_filter_from.setCalendarPopup(True)
        self._clip_filter_from.setDisplayFormat("yyyy-MM-dd")
        self._clip_filter_from.setMinimumDate(QDate(1970, 1, 1))
        self._clip_filter_from.setSpecialValueText("From")
        self._clip_filter_from.setDate(self._clip_filter_from.minimumDate())
        self._clip_filter_from.setFixedHeight(SIZE_CONTROL_MD)
        self._clip_filter_from.setMinimumWidth(140)
        self._clip_filter_from.setStyleSheet(_FORM_INPUTS)
        row2.addWidget(self._clip_filter_from)

        self._clip_filter_to = QDateEdit()
        self._clip_filter_to.setCalendarPopup(True)
        self._clip_filter_to.setDisplayFormat("yyyy-MM-dd")
        self._clip_filter_to.setMinimumDate(QDate(1970, 1, 1))
        self._clip_filter_to.setSpecialValueText("To")
        self._clip_filter_to.setDate(self._clip_filter_to.minimumDate())
        self._clip_filter_to.setFixedHeight(SIZE_CONTROL_MD)
        self._clip_filter_to.setMinimumWidth(140)
        self._clip_filter_to.setStyleSheet(_FORM_INPUTS)
        row2.addWidget(self._clip_filter_to)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(SIZE_CONTROL_MD)
        clear_btn.setStyleSheet(_SECONDARY_BTN)
        row2.addWidget(clear_btn)
        fl.addLayout(row2)

        action_row = QHBoxLayout()
        action_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(SIZE_CONTROL_MD)
        close_btn.setStyleSheet(_SECONDARY_BTN)
        close_btn.clicked.connect(dlg.close)
        action_row.addWidget(close_btn)
        fl.addLayout(action_row)

        self._clip_filter_face.textChanged.connect(self._on_clip_filters_changed)
        self._clip_filter_camera.currentIndexChanged.connect(self._on_clip_filters_changed)
        self._clip_filter_rule.currentIndexChanged.connect(self._on_clip_filters_changed)
        self._clip_filter_object.currentIndexChanged.connect(self._on_clip_filters_changed)
        self._clip_filter_from.dateChanged.connect(self._on_clip_filters_changed)
        self._clip_filter_to.dateChanged.connect(self._on_clip_filters_changed)
        clear_btn.clicked.connect(self._clear_clip_filters)

        self._clip_filters_dialog = dlg

    def _open_clip_filters_dialog(self) -> None:
        self._ensure_clip_filters_dialog()
        if not self._clip_filters_dialog:
            return
        if self._clip_filters_dialog.isVisible():
            self._clip_filters_dialog.raise_()
            self._clip_filters_dialog.activateWindow()
            return
        btn = self._filters_btn
        if btn:
            pos = btn.mapToGlobal(btn.rect().bottomLeft())
            dialog_w = self._clip_filters_dialog.width()
            x = pos.x() - dialog_w + btn.width()
            y = pos.y() + SPACE_6
            self._clip_filters_dialog.move(x, y)
        self._clip_filters_dialog.show()

    def _load_clip_filters(self) -> None:
        if not self._clip_filter_camera:
            return
        self._clip_filter_camera.clear()
        self._clip_filter_camera.addItem("All Cameras", -1)
        try:
            for cam in db.get_cameras(enabled_only=False) or []:
                self._clip_filter_camera.addItem(cam.get("name", f"Camera {cam.get('id')}"), int(cam.get("id")))
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            pass

        self._clip_filter_rule.clear()
        self._clip_filter_rule.addItem("Any Rule", "")
        try:
            for rule in db.get_rules(enabled_only=False) or []:
                self._clip_filter_rule.addItem(rule.get("name", "Rule"), rule.get("name", ""))
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            pass

        self._clip_filter_object.clear()
        self._clip_filter_object.addItem("Any Object", "")
        try:
            classes = db.get_plugin_classes(enabled_only=True) or []
            seen = set()
            for cls in classes:
                name = cls.get("class_name")
                if name and name not in seen:
                    seen.add(name)
                    self._clip_filter_object.addItem(name, name)
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            pass

    def _on_clip_filters_changed(self, _value=None) -> None:
        if not self._filters_ready or not hasattr(self, "_clips_list"):
            return
        self._refresh_clips_list()

    def _clear_clip_filters(self) -> None:
        self._clip_filter_face.setText("")
        self._clip_filter_camera.setCurrentIndex(0)
        self._clip_filter_rule.setCurrentIndex(0)
        self._clip_filter_object.setCurrentIndex(0)
        self._clip_filter_from.setDate(self._clip_filter_from.minimumDate())
        self._clip_filter_to.setDate(self._clip_filter_to.minimumDate())
        self._refresh_clips_list()

    def _get_clip_filter_values(self) -> dict:
        camera_id = self._clip_filter_camera.currentData()
        face_label = self._clip_filter_face.text().strip()
        rule_name = self._clip_filter_rule.currentData()
        object_type = self._clip_filter_object.currentData()

        ts_from = None
        ts_to = None
        min_date = self._clip_filter_from.minimumDate()
        has_from = self._clip_filter_from.date() != min_date
        has_to = self._clip_filter_to.date() != min_date
        if has_from and has_to:
            start = qdate_to_date(self._clip_filter_from.date())
            end = qdate_to_date(self._clip_filter_to.date())
            date_range = normalize_date_range(start, end)
            if date_range.swapped:
                self._clip_filter_from.setDate(QDate(date_range.start.year, date_range.start.month, date_range.start.day))
                self._clip_filter_to.setDate(QDate(date_range.end.year, date_range.end.month, date_range.end.day))
            ts_from, ts_to = day_timestamp_bounds(date_range.start, date_range.end)
        elif has_from:
            start = qdate_to_date(self._clip_filter_from.date())
            ts_from, _ = day_timestamp_bounds(start, start)
        elif has_to:
            end = qdate_to_date(self._clip_filter_to.date())
            _, ts_to = day_timestamp_bounds(end, end)

        return {
            "camera_id": camera_id,
            "face_label": face_label or None,
            "rule_triggered": rule_name or None,
            "object_type": object_type or None,
            "ts_from": ts_from,
            "ts_to": ts_to,
        }

    @staticmethod
    def _parse_clip_filename(name: str) -> tuple[int | None, int | None, str]:
        if name.startswith("clip_cam") and "_" in name:
            try:
                rest = name.replace("clip_cam", "", 1)
                cam_part, ts_part = rest.split("_", 1)
                cam_id = int(cam_part)
                ts = int(ts_part.split(".", 1)[0])
                return cam_id, ts, "live"
            except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
                return None, None, "live"
        if name.startswith("clip_"):
            try:
                ts = int(name.replace("clip_", "", 1).split(".", 1)[0])
                return None, ts, "playback"
            except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
                return None, None, "playback"
        return None, None, "playback"

    def _sync_clips_index(self) -> None:
        try:
            existing = {row.get("path") for row in db.get_clips() or []}
        except (sqlite3.Error, OSError, TypeError, ValueError):
            logger.warning("Failed to read existing clips index", exc_info=True)
            existing = set()
        for folder in ("data/clips_live", "data/clips"):
            if not os.path.isdir(folder):
                continue
            for name in os.listdir(folder):
                if not name.lower().endswith((".mp4", ".avi", ".mkv", ".mov", ".wmv")):
                    continue
                path = os.path.join(folder, name)
                if path in existing:
                    continue
                cam_id, ts, source = self._parse_clip_filename(name)
                if ts is None:
                    try:
                        ts = int(os.path.getmtime(path))
                    except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
                        ts = None
                try:
                    db.add_clip(path, source, cam_id, ts, None, [], [])
                except (sqlite3.Error, OSError, TypeError, ValueError):
                    logger.warning("Failed to index clip path=%s", path, exc_info=True)

    def _refresh_clips_list(self) -> None:
        selected_path = None
        cur = self._clips_list.currentItem()
        if cur:
            selected_path = cur.data(Qt.ItemDataRole.UserRole)
        self._clips_list.clear()
        self._clip_cards.clear()
        self._sync_clips_index()
        filters = self._get_clip_filter_values()
        try:
            rows = db.get_clips(
                camera_id=filters["camera_id"],
                ts_from=filters["ts_from"],
                ts_to=filters["ts_to"],
                face_label=filters["face_label"],
                object_type=filters["object_type"],
                rule_triggered=filters["rule_triggered"],
            )
        except (sqlite3.Error, OSError, TypeError, ValueError):
            logger.warning("Failed to load filtered clips", exc_info=True)
            rows = []

        if not rows:
            self._clip_status.setText("No clips saved yet")
            return
        selected_item = None
        for row in rows:
            path = row.get("path")
            if not path or not os.path.exists(path):
                continue
            ts = row.get("ts")
            if not ts:
                try:
                    ts = int(os.path.getmtime(path))
                except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
                    ts = 0
            source = row.get("source") or "playback"
            name = os.path.splitext(os.path.basename(path))[0]
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setSizeHint(QSize(0, SIZE_ROW_XL))
            row_w = ClipRowWidget(name, source, ts, path)
            row_w.clicked.connect(lambda _=False, lw=self._clips_list, it=item: _set_list_active(lw, it, self._on_clip_item_activated))
            row_w.set_delete_callback(lambda p=path: self._delete_clip(p))
            self._clips_list.addItem(item)
            self._clips_list.setItemWidget(item, row_w)
            self._clip_cards.append((item, row_w))
            if selected_path and path == selected_path:
                selected_item = item
        if selected_item:
            self._clips_list.setCurrentItem(selected_item)
        self._sync_clip_card_selection(self._clips_list.currentItem(), None)

    def _on_clip_item_activated(self, item) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self._start_playback(path)

    def _sync_clip_card_selection(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        for it, card in self._clip_cards:
            card.set_active(it is current)

    def _delete_clip(self, path: str) -> None:
        try:
            if path and os.path.exists(path):
                os.remove(path)
            try:
                db.delete_clip(path)
            except (sqlite3.Error, OSError, ValueError):
                logger.warning("Failed to delete clip from database path=%s", path, exc_info=True)
            self._clip_status.setText(f"Deleted: {os.path.basename(path)}")
        except OSError as e:
            self._clip_status.setText(f"Delete failed: {e}")
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError) as e:
            logger.exception("Unexpected clip deletion failure path=%s", path)
            self._clip_status.setText(f"Delete failed: {e}")
        self._refresh_clips_list()
    def _load_rule_cameras(self) -> None:
        self._rule_combo.clear()
        self._rule_combo.addItem("Global (no camera)", -1)
        cams = []
        try:
            cams = db.get_cameras(enabled_only=True)
        except (RuntimeError, AttributeError, TypeError, ValueError, OSError):
            cams = []
        for cam in cams:
            self._rule_combo.addItem(cam.get("name", f"Camera {cam.get('id')}"), int(cam.get("id")))
        if cams:
            self._rule_camera_id = int(cams[0].get("id"))
            self._rule_combo.setCurrentIndex(1)
        else:
            self._rule_camera_id = -1
            self._rule_combo.setCurrentIndex(0)

    def _on_rule_camera_changed(self, idx: int) -> None:
        if idx < 0:
            return
        self._rule_camera_id = int(self._rule_combo.currentData())
        if self._playback_thread and self._path_edit.text():
            self._start_playback(self._path_edit.text())

    def _start_playback(self, path: str) -> None:
        self._stop()
        self._path_edit.setText(path)
        self._playback_thread = PlaybackThread(path, virtual_camera_id=self._rule_camera_id)
        self._playback_thread.set_detection_enabled(self._detect_toggle.isChecked())
        self._playback_thread.set_record_enabled(self._record_toggle.isChecked())
        self._playback_thread.frame_ready.connect(self._on_frame)
        self._playback_thread.detection_event.connect(self._on_detection_event)
        self._playback_thread.playback_finished.connect(self._on_finished)
        self._playback_thread.clip_saved.connect(self._on_clip_saved)
        self._playback_thread.clip_failed.connect(self._on_clip_failed)
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            self._total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            self._video_fps = fps
            self._fps_label.setText(f"FPS: {fps:.0f}")
            total_sec = self._total_frames / fps
            self._time_label.setText(f"00:00:00 / {self._format_time(total_sec)}")
            self._timeline_slider.setRange(0, max(0, self._total_frames - 1))
            cap.release()
        self._events_list.clear()
        self._events = []
        self._saved_clips = []
        self._event_badge.setText("0")
        self._refresh_clips_list()
        self._clip_status.setText("")
        self._playback_thread.start()
        self._sync_play_button(paused=False)
        self._apply_speed()

    def _sync_play_button(self, paused: bool) -> None:
        icon_path = "frontend/assets/icons/play.png" if paused else "frontend/assets/icons/pause.png"
        pix = themed_icon_pixmap(icon_path, int(SIZE_SECTION_H * 0.52), int(SIZE_SECTION_H * 0.52))
        if not pix.isNull():
            self._play_btn.setIcon(QIcon(pix))
            self._play_btn.setIconSize(QSize(int(SIZE_SECTION_H * 0.52), int(SIZE_SECTION_H * 0.52)))

    @staticmethod
    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

