from __future__ import annotations

import os

import cv2
from PySide6.QtCore import Qt, QSize, QSettings
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from backend.camera.playback_thread import PlaybackThread
from backend.repository import db
from frontend.app_theme import page_base_styles, safe_set_point_size
from frontend.widgets.toggle_switch import ToggleSwitch
from frontend.widgets.video_widget import VideoWidget


from frontend.styles._colors import (
    _ACCENT,
    _ACCENT_BG_18,
    _ACCENT_BG_22,
    _ACCENT_HI,
    _ACCENT_HI_BG_07,
    _ACCENT_HI_BG_22,
    _ACCENT_HI_BG_45,
    _BG_BASE,
    _BG_OVERLAY,
    _BG_RAISED,
    _BG_SURFACE,
    _BLACK,
    _BORDER,
    _BORDER_DIM,
    _DANGER,
    _SUCCESS,
    _TEXT_MUTED,
    _TEXT_PRI,
    _TEXT_SEC,
)
from frontend.styles._input_styles import _FORM_INPUTS, _FORM_COMBO
from frontend.styles._btn_styles import _PRIMARY_BTN, _ICON_BTN, _ICON_BTN_DANGER
from frontend.styles.page_styles import header_bar_style, toolbar_style
from frontend.ui_tokens import (
    FONT_SIZE_CAPTION,
    FONT_SIZE_HEADING,
    FONT_SIZE_LABEL,
    FONT_SIZE_MICRO,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_HEAVY,
    FONT_WEIGHT_SEMIBOLD,
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
    SIZE_SECTION_H,
    SIZE_TOOLBAR_H,
    SPACE_10,
    SPACE_14,
    SPACE_18,
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
{_FORM_INPUTS}
{_FORM_COMBO}
QSlider::groove:horizontal {{
    height: {SPACE_XS}px; background: {_BG_OVERLAY}; border-radius: {RADIUS_XS}px;
}}
QSlider::handle:horizontal {{
    background: {_ACCENT_HI}; border: {SPACE_XXS}px solid {_ACCENT};
    width: {SPACE_14}px; height: {SPACE_14}px; margin: -{SPACE_5}px 0; border-radius: {RADIUS_MD}px;
}}
QSlider::sub-page:horizontal {{ background: {_ACCENT}; border-radius: {RADIUS_XS}px; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{
    padding: {SPACE_10}px {SPACE_14}px; color: {_TEXT_SEC}; border-radius: {RADIUS_6}px; background: transparent;
}}
QListWidget::item:selected {{ background: {_ACCENT_BG_18}; color: {_TEXT_PRI}; }}
QListWidget::item:hover:!selected {{ background: {_ACCENT_HI_BG_07}; color: {_TEXT_PRI}; }}
QListWidget#clips_list::item {{ padding: {SPACE_6}px {SPACE_10}px; color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; }}
QListWidget#clips_list::item:selected {{ color: {_TEXT_PRI}; }}
QScrollBar:vertical {{ border: none; background: transparent; width: {SPACE_6}px; margin: {SPACE_XXS}px 0; }}
    QScrollBar::handle:vertical {{
        background: {_ACCENT_HI_BG_22}; min-height: {SIZE_CONTROL_SM}px; border-radius: {RADIUS_3}px;
    }}
QScrollBar::handle:vertical:hover {{ background: {_ACCENT_HI_BG_45}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
)


def _icon_btn(icon_path: str, size: int = 36, danger: bool = False) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(size, size)
    btn.setStyleSheet(_ICON_BTN_DANGER if danger else _ICON_BTN)
    pix = QPixmap(icon_path)
    if not pix.isNull():
        btn.setIcon(QIcon(pix))
        btn.setIconSize(QSize(int(size * 0.52), int(size * 0.52)))
    return btn


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
        pix = QPixmap("frontend/assets/icons/playback.png")
        if not pix.isNull():
            icon_lbl.setPixmap(
                pix.scaled(SIZE_CONTROL_SM, SIZE_CONTROL_SM, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        hl.addWidget(icon_lbl)

        title = QLabel("Playback & Review")
        tf = QFont()
        safe_set_point_size(tf, FONT_SIZE_HEADING)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(f"color: {_TEXT_PRI};")
        hl.addWidget(title)
        hl.addStretch()

        self._fps_label = QLabel("FPS: —")
        self._fps_label.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_LABEL}px;")
        hl.addWidget(self._fps_label)

        self._time_label = QLabel("00:00:00 / 00:00:00")
        self._time_label.setStyleSheet(f"color: {_TEXT_SEC}; font-size: {FONT_SIZE_LABEL}px; padding-left: {SPACE_LG}px;")
        hl.addWidget(self._time_label)
        root.addWidget(header_w)

        toolbar = QWidget()
        toolbar.setFixedHeight(SIZE_TOOLBAR_H)
        toolbar.setStyleSheet(toolbar_style(bg=_BG_SURFACE, border=_BORDER_DIM))
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(SPACE_XL, 0, SPACE_XL, 0)
        tl.setSpacing(SPACE_MD)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select a video file to begin…")
        self._path_edit.setReadOnly(True)
        self._path_edit.setFixedHeight(SIZE_CONTROL_MD)
        _folder_act = self._path_edit.addAction(
            QIcon("frontend/assets/icons/folder.png"),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        _folder_act.triggered.connect(self._open_file)
        tl.addWidget(self._path_edit, stretch=1)

        _sep1 = QWidget()
        _sep1.setFixedSize(SPACE_XXXS, SPACE_XL)
        _sep1.setStyleSheet(f"background: {_BORDER_DIM};")
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
        _sep2.setStyleSheet(f"background: {_BORDER_DIM};")
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

        _sep3 = QWidget()
        _sep3.setFixedSize(SPACE_XXXS, SPACE_XL)
        _sep3.setStyleSheet(f"background: {_BORDER_DIM};")
        tl.addWidget(_sep3)

        rule_lbl = QLabel("Rules")
        rule_lbl.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; font-weight: {FONT_WEIGHT_BOLD}; letter-spacing: 0.{SPACE_XS}px;"
        )
        tl.addWidget(rule_lbl)
        self._rule_combo = QComboBox()
        self._rule_combo.setFixedHeight(SIZE_SECTION_H)
        self._rule_combo.setFixedWidth(SIZE_DIALOG_W)
        self._rule_combo.setStyleSheet(_FORM_COMBO)
        self._rule_combo.currentIndexChanged.connect(self._on_rule_camera_changed)
        tl.addWidget(self._rule_combo)
        root.addWidget(toolbar)

        content = QWidget()
        content.setStyleSheet(f"background: {_BG_BASE};")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(SPACE_20, SPACE_LG, SPACE_20, SPACE_LG)
        cl.setSpacing(SPACE_MD)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(SPACE_SM)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        left = QWidget()
        left.setStyleSheet("background: transparent;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(SPACE_10)

        self._video_widget = VideoWidget()
        self._video_widget.setMinimumSize(480, 280)
        self._video_widget.setStyleSheet(f"background: {_BLACK}; border-radius: {RADIUS_LG}px;")
        ll.addWidget(self._video_widget, stretch=1)

        ctrl_card = QWidget()
        ctrl_card.setStyleSheet(f"background: {_BG_RAISED}; border-radius: {RADIUS_LG}px;")
        cc = QVBoxLayout(ctrl_card)
        cc.setContentsMargins(SPACE_LG, SPACE_MD, SPACE_LG, SPACE_MD)
        cc.setSpacing(SPACE_10)

        self._timeline_slider = QSlider(Qt.Orientation.Horizontal)
        self._timeline_slider.setRange(0, 100)
        self._timeline_slider.setValue(0)
        self._timeline_slider.sliderReleased.connect(self._on_seek)
        cc.addWidget(self._timeline_slider)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(SPACE_6)

        self._play_btn = _icon_btn("frontend/assets/icons/play.png", SIZE_SECTION_H)
        self._play_btn.setToolTip("Play / Resume")
        self._play_btn.clicked.connect(self._toggle_play)
        ctrl_row.addWidget(self._play_btn)

        self._pause_btn = _icon_btn("frontend/assets/icons/pause.png", SIZE_SECTION_H)
        self._pause_btn.setToolTip("Pause")
        self._pause_btn.clicked.connect(self._pause)
        ctrl_row.addWidget(self._pause_btn)

        self._stop_btn = _icon_btn("frontend/assets/icons/stop.png", SIZE_SECTION_H, danger=True)
        self._stop_btn.setToolTip("Stop")
        self._stop_btn.clicked.connect(self._stop)
        ctrl_row.addWidget(self._stop_btn)

        _div = QWidget()
        _div.setFixedSize(SPACE_XXXS, SIZE_PILL_H)
        _div.setStyleSheet(f"background: {_BORDER_DIM};")
        ctrl_row.addSpacing(SPACE_6)
        ctrl_row.addWidget(_div)
        ctrl_row.addSpacing(SPACE_6)

        speed_lbl = QLabel("Speed")
        speed_lbl.setStyleSheet(f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_CAPTION}px; font-weight: {FONT_WEIGHT_BOLD};")
        ctrl_row.addWidget(speed_lbl)

        self._speed_combo = QComboBox()
        self._speed_combo.addItems(["0.25×", "0.5×", "1×", "2×", "4×"])
        self._speed_combo.setCurrentIndex(2)
        self._speed_combo.setFixedWidth(SIZE_FIELD_W_XS)
        self._speed_combo.setFixedHeight(SIZE_SECTION_H)
        self._speed_combo.currentIndexChanged.connect(self._change_speed)
        ctrl_row.addWidget(self._speed_combo)

        ctrl_row.addStretch()

        snap_btn = QPushButton("  Snapshot")
        snap_btn.setFixedHeight(SIZE_SECTION_H)
        snap_btn.setStyleSheet(_PRIMARY_BTN)
        snap_btn.clicked.connect(self._save_snapshot)
        ctrl_row.addWidget(snap_btn)

        cc.addLayout(ctrl_row)
        ll.addWidget(ctrl_card)
        splitter.addWidget(left)

        right = QWidget()
        right.setMinimumWidth(200)
        right.setMaximumWidth(SIZE_DIALOG_W)
        right.setStyleSheet("background: transparent;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setHandleWidth(SPACE_SM)
        right_split.setStyleSheet("QSplitter::handle { background: transparent; }")

        events_card = QWidget()
        events_card.setStyleSheet(f"background: {_BG_RAISED}; border-radius: {RADIUS_LG}px;")
        ec = QVBoxLayout(events_card)
        ec.setContentsMargins(0, 0, 0, SPACE_MD)
        ec.setSpacing(0)

        ev_hdr_w = QWidget()
        ev_hdr_w.setFixedHeight(SIZE_CONTROL_LG)
        ev_hdr_w.setStyleSheet("background: transparent;")
        ev_hdr_l = QHBoxLayout(ev_hdr_w)
        ev_hdr_l.setContentsMargins(SPACE_LG, 0, SPACE_MD, 0)
        ev_hdr_l.setSpacing(SPACE_SM)

        ev_title = QLabel("DETECTION EVENTS")
        ev_title.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY}; letter-spacing: {SPACE_XXXS}px;"
        )
        ev_hdr_l.addWidget(ev_title)
        ev_hdr_l.addStretch()

        self._event_badge = QLabel("0")
        self._event_badge.setFixedSize(SIZE_PILL_H, SIZE_PILL_H)
        self._event_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._event_badge.setStyleSheet(
            f"background: {_BG_OVERLAY}; color: {_TEXT_MUTED};"
            f" border-radius: {RADIUS_11}px; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_BOLD};"
        )
        ev_hdr_l.addWidget(self._event_badge)
        ec.addWidget(ev_hdr_w)

        self._events_list = QListWidget()
        self._events_list.setAlternatingRowColors(True)
        self._events_list.viewport().setAutoFillBackground(False)
        self._events_list.viewport().setStyleSheet("background: transparent;")
        self._events_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._events_list.itemClicked.connect(self._on_event_clicked)
        ec.addWidget(self._events_list, stretch=1)

        right_split.addWidget(events_card)

        clips_card = QWidget()
        clips_card.setStyleSheet(f"background: {_BG_RAISED}; border-radius: {RADIUS_LG}px;")
        ccv = QVBoxLayout(clips_card)
        ccv.setContentsMargins(0, 0, 0, SPACE_MD)
        ccv.setSpacing(0)

        clips_hdr_w = QWidget()
        clips_hdr_w.setFixedHeight(SIZE_CONTROL_LG)
        clips_hdr_w.setStyleSheet("background: transparent;")
        clips_hdr_l = QHBoxLayout(clips_hdr_w)
        clips_hdr_l.setContentsMargins(SPACE_LG, 0, SPACE_MD, 0)
        clips_hdr_l.setSpacing(SPACE_SM)

        clips_title = QLabel("SAVED CLIPS")
        clips_title.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; font-weight: {FONT_WEIGHT_HEAVY}; letter-spacing: {SPACE_XXXS}px;"
        )
        clips_hdr_l.addWidget(clips_title)
        clips_hdr_l.addStretch()
        ccv.addWidget(clips_hdr_w)

        self._clips_list = QListWidget()
        self._clips_list.setObjectName("clips_list")
        self._clips_list.setAlternatingRowColors(True)
        self._clips_list.viewport().setAutoFillBackground(False)
        self._clips_list.viewport().setStyleSheet("background: transparent;")
        self._clips_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._clips_list.itemClicked.connect(self._on_clip_item_activated)
        ccv.addWidget(self._clips_list, stretch=1)

        self._clip_status = QLabel("")
        self._clip_status.setStyleSheet(
            f"color: {_TEXT_MUTED}; font-size: {FONT_SIZE_MICRO}px; padding: 0 {SPACE_LG}px {SPACE_SM}px {SPACE_LG}px;"
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

    def _on_frame(self, camera_id, frame, state) -> None:
        frame_idx = state.get("frame_index", 0)
        self._current_frame = frame_idx
        self._video_widget.update_frame(frame, state)
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
        desc = ", ".join(rules) if rules else f"Frame {frame_idx}"
        self._events_list.addItem(QListWidgetItem(f"[{frame_idx}]  {desc}"))
        self._event_badge.setText(str(len(self._events)))

    def _on_clip_saved(self, path: str) -> None:
        self._saved_clips.append(path)
        self._refresh_clips_list()
        self._clip_status.setText(f"Saved: {os.path.basename(path)}")

    def _on_clip_failed(self, message: str) -> None:
        self._clip_status.setText(message)

    def _on_detection_toggled(self, state: bool) -> None:
        if self._playback_thread:
            self._playback_thread.set_detection_enabled(state)

    def _on_record_toggled(self, state: bool) -> None:
        if self._playback_thread:
            self._playback_thread.set_record_enabled(state)

    def _on_event_clicked(self, item) -> None:
        idx = self._events_list.row(item)
        if idx < len(self._events):
            frame_idx, _ = self._events[idx]
            if self._playback_thread:
                self._playback_thread.seek(frame_idx)

    def _on_finished(self, camera_id=None) -> None:
        pass

    def _toggle_play(self) -> None:
        if self._playback_thread is None:
            return
        if self._playback_thread.is_paused:
            self._playback_thread.resume()
        else:
            self._playback_thread.pause()

    def _pause(self) -> None:
        if self._playback_thread:
            self._playback_thread.pause()

    def _stop(self) -> None:
        if self._playback_thread:
            self._playback_thread.stop()
            self._playback_thread.wait(2000)
            self._playback_thread = None
        self._video_widget.show_placeholder("No video loaded")
        self._timeline_slider.setValue(0)
        self._fps_label.setText("FPS: —")
        self._time_label.setText("00:00:00 / 00:00:00")

    def _on_seek(self) -> None:
        if self._playback_thread:
            self._playback_thread.seek(self._timeline_slider.value())

    def _change_speed(self, idx: int) -> None:
        speeds = [0.25, 0.5, 1.0, 2.0, 4.0]
        if self._playback_thread and idx < len(speeds):
            self._playback_thread.set_fps_limit(int(30 * speeds[idx]))

    def _save_snapshot(self) -> None:
        if not hasattr(self._video_widget, "_last_frame") or self._video_widget._last_frame is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Snapshot", "snapshot.jpg", "JPEG (*.jpg);;PNG (*.png)")
        if path:
            cv2.imwrite(path, self._video_widget._last_frame)

    def _refresh_clips_list(self) -> None:
        self._clips_list.clear()
        entries: list[tuple[float, str, str]] = []
        for folder, tag in (("data/clips_live", "live"), ("data/clips", "playback")):
            if not os.path.isdir(folder):
                continue
            for name in os.listdir(folder):
                if not name.lower().endswith((".mp4", ".avi", ".mkv", ".mov", ".wmv")):
                    continue
                path = os.path.join(folder, name)
                try:
                    ts = os.path.getmtime(path)
                except Exception:
                    ts = 0.0
                entries.append((ts, tag, path))
        entries.sort(key=lambda x: x[0], reverse=True)
        if not entries:
            self._clip_status.setText("No clips saved yet")
            return
        for _ts, tag, path in entries:
            name = os.path.basename(path)
            item = QListWidgetItem(f"[{tag}] {name}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._clips_list.addItem(item)

    def _on_clip_item_activated(self, item) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self._start_playback(path)
    def _load_rule_cameras(self) -> None:
        self._rule_combo.clear()
        self._rule_combo.addItem("Global (no camera)", -1)
        cams = []
        try:
            cams = db.get_cameras(enabled_only=True)
        except Exception:
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
            self._timeline_slider.setRange(0, self._total_frames)
            cap.release()
        self._events_list.clear()
        self._events = []
        self._saved_clips = []
        self._event_badge.setText("0")
        self._refresh_clips_list()
        self._clip_status.setText("")
        self._playback_thread.start()

    @staticmethod
    def _format_time(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
