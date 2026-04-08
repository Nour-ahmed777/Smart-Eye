import collections
import logging
import os
import time

import cv2
import numpy as np
from PySide6.QtCore import QMutex, QThread, Signal

from backend.pipeline.detector_manager import get_manager
from backend.pipeline.inference_utils import build_state
from backend.services.pipeline_service import PipelineService
from backend.repository import db


class PlaybackThread(QThread):
    frame_ready = Signal(int, np.ndarray, dict)
    playback_finished = Signal(int)
    position_changed = Signal(int, int, int)
    detection_event = Signal(int, int, dict)
    clip_saved = Signal(str)
    clip_failed = Signal(str)

    def __init__(self, video_path, virtual_camera_id=-1, fps_limit=30, parent=None):
        super().__init__(parent)
        self._video_path = video_path
        self._camera_id = virtual_camera_id
        self._fps_limit = fps_limit
        self._fps_lock = QMutex()
        self._running = False
        self._paused = False
        self._seek_frame = -1
        self._cap = None
        self._total_frames = 0
        self._detection_events = []
        self._detection_enabled = False
        self._record_enabled = False
        self._frame_buffer: collections.deque = collections.deque()
        self._video_fps_actual: float = 30.0

    @property
    def camera_id(self):
        return self._camera_id

    def run(self):
        self._running = True
        self._cap = cv2.VideoCapture(self._video_path)
        if not self._cap.isOpened():
            logging.getLogger(__name__).warning("Playback: failed to open video %s", self._video_path)
            self.playback_finished.emit(self._camera_id)
            return
        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = self._cap.get(cv2.CAP_PROP_FPS) or 30
        self._video_fps_actual = video_fps
        logging.getLogger(__name__).info(
            "Playback: start path=%s frames=%s fps=%.2f cam_id=%s",
            self._video_path,
            self._total_frames,
            video_fps,
            self._camera_id,
        )
        buf_max = int(video_fps * 5)
        detector = get_manager()
        pipeline = PipelineService(self._camera_id)
        frame_idx = 0
        _clip_cooldown = 0

        def _evaluate_frame(frame, w, h):
            detection_results = detector.process_frame(frame, self._camera_id)
            return build_state(detection_results, self._camera_id, w, h)

        def _handle_triggers(primary_state, triggered, frame, frame_idx, video_fps, fw, fh):
            nonlocal _clip_cooldown

            def _on_event(trig, state):
                nonlocal _clip_cooldown
                logging.getLogger(__name__).info(
                    "Playback: rule trigger cam_id=%s frame=%s rules=%s record=%s buffer=%s cooldown=%s",
                    self._camera_id,
                    frame_idx,
                    [r.get("name") for r in trig],
                    self._record_enabled,
                    len(self._frame_buffer),
                    _clip_cooldown,
                )
                event = {
                    "frame": frame_idx,
                    "rules": [r["name"] for r in trig],
                    "state": state,
                }
                self._detection_events.append(event)
                self.detection_event.emit(self._camera_id, frame_idx, state)
                if self._record_enabled and self._frame_buffer and _clip_cooldown <= 0:
                    if self._save_clip(video_fps, state, [r.get("name") for r in trig]):
                        _clip_cooldown = int(video_fps * 5)

            primary_state["_triggered"] = triggered
            pipeline.handle_result(
                primary_state,
                frame,
                infer_fw=fw,
                infer_fh=fh,
                enable_inbox=False,
                enable_heatmap=False,
                on_detection_event=_on_event,
            )

        while self._running:
            force_read = False
            if self._seek_frame >= 0:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, self._seek_frame)
                frame_idx = self._seek_frame
                self._seek_frame = -1
                force_read = True
            if self._paused and not force_read:
                time.sleep(0.05)
                continue
            t_start = time.time()
            ret, frame = self._cap.read()
            if not ret:
                logging.getLogger(__name__).info("Playback: reached end of video")
                self.playback_finished.emit(self._camera_id)
                break

            if self._record_enabled and not self._paused:
                self._frame_buffer.append(frame.copy())
                while len(self._frame_buffer) > buf_max:
                    self._frame_buffer.popleft()

            h, w = frame.shape[:2]
            if self._detection_enabled:
                primary_state, all_triggered = _evaluate_frame(frame, w, h)
                _handle_triggers(primary_state, all_triggered, frame, frame_idx, video_fps, w, h)
            else:
                all_triggered = []
                primary_state = {"triggered_rules": [], "frame_index": frame_idx}
            primary_state["triggered_rules"] = [r["name"] for r in all_triggered]
            primary_state["frame_index"] = frame_idx

            if _clip_cooldown > 0:
                _clip_cooldown -= 1

            self.position_changed.emit(self._camera_id, frame_idx, self._total_frames)
            self.frame_ready.emit(self._camera_id, frame, primary_state)
            if not self._paused:
                frame_idx += 1
            elapsed = time.time() - t_start
            self._fps_lock.lock()
            try:
                fps_limit = self._fps_limit
            finally:
                self._fps_lock.unlock()
            frame_delay = 1.0 / max(0.25, fps_limit)
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        if self._cap:
            self._cap.release()

    def _save_clip(self, fps: float, state: dict | None = None, rules: list[str] | None = None) -> str | None:
        try:
            os.makedirs("data/clips", exist_ok=True)
            fname = os.path.join("data", "clips", f"clip_{int(time.time())}.mp4")
            frames = list(self._frame_buffer)
            if not frames:
                logging.getLogger(__name__).warning("Playback: no buffered frames; skipping clip save")
                return None
            h, w = frames[0].shape[:2]
            fourcc = cv2.VideoWriter.fourcc(*"mp4v")
            writer = cv2.VideoWriter(fname, fourcc, fps, (w, h))
            if not writer.isOpened():
                raise RuntimeError("VideoWriter failed to open (mp4v)")
            for f in frames:
                writer.write(f)
            writer.release()
            self.clip_saved.emit(fname)
            logging.getLogger(__name__).info("Playback: clip saved %s", fname)
            try:
                det = (state or {}).get("detections", {}) or {}
                obj_types = [
                    k
                    for k, v in det.items()
                    if k not in ("identity", "gender") and v not in (False, 0, "unknown", None, "none")
                ]
                db.add_clip(
                    fname,
                    "playback",
                    self._camera_id,
                    int(time.time()),
                    (state or {}).get("identity"),
                    rules or [],
                    obj_types,
                )
            except Exception:
                logging.getLogger(__name__).exception("Playback: failed to record clip metadata")
            return fname
        except Exception as e:
            msg = f"Clip save failed: {e}"
            logging.getLogger(__name__).exception("Playback: failed to save clip")
            self.clip_failed.emit(msg)
            return None

    def stop(self):
        self._running = False
        self.wait(3000)

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def seek(self, frame_number):
        self._seek_frame = frame_number

    def set_detection_enabled(self, enabled: bool):
        self._detection_enabled = enabled

    def set_record_enabled(self, enabled: bool):
        self._record_enabled = enabled
        if not enabled:
            self._frame_buffer.clear()

    def set_fps_limit(self, fps_limit: float) -> None:
        self._fps_lock.lock()
        try:
            self._fps_limit = max(0.25, float(fps_limit))
        finally:
            self._fps_lock.unlock()

    @property
    def total_frames(self):
        return self._total_frames

    @property
    def is_paused(self):
        return self._paused
