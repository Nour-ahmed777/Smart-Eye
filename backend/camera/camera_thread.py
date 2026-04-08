import time
import contextlib
import logging
import collections
from concurrent.futures import Future, ThreadPoolExecutor

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
import os

from backend.repository import db
from backend.pipeline.detector_manager import get_manager
from backend.pipeline.inference_utils import build_state
from backend.services.pipeline_service import PipelineService
from backend.services.service_manager import get_service_manager

_DEFAULT_INFER_INTERVAL = 3


class CameraThread(QThread):
    frame_ready = Signal(int, np.ndarray, dict)
    error_occurred = Signal(int, str)
    reconnecting = Signal(int)
    fps_updated = Signal(int, float)

    def __init__(self, camera_id, source, fps_limit=30, parent=None):
        super().__init__(parent)
        self._camera_id = camera_id
        self._source = source
        self._fps_limit = fps_limit
        self._running = False
        self._cap = None
        self._frame_count = 0
        self._fps = 0.0
        self._last_fps_time = 0
        self._infer_interval = _DEFAULT_INFER_INTERVAL
        self._raw_source = source
        self._is_twitch = "twitch.tv/" in str(source)
        self._last_inbox_save_ts = 0.0
        self._recent_inbox_embs: list[tuple[float, np.ndarray]] = []
        self._inbox_enabled = False
        self._suppress_errors = False
        self._clip_enabled = True
        self._clip_seconds = 5
        self._clip_buffer: collections.deque[tuple[float, np.ndarray]] = collections.deque()
        self._last_clip_ts = 0.0
        self._clip_recent: dict[tuple[str, tuple[str, ...]], float] = {}
        self._clip_min_interval = 10.0
        self._clip_repeat_window = 60.0

    @property
    def camera_id(self):
        return self._camera_id

    @property
    def fps(self):
        return self._fps

    def set_inference_interval(self, n: int):
        self._infer_interval = max(1, n)

    def run(self):
        self._running = True
        try:
            os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_MSMF", "1")
            os.environ.setdefault("OPENCV_VIDEOIO_DISABLE_DIRECTSHOW", "1")
            configured_prefixes = db.get_setting("live_stream_prefixes", None)
            http_as_live = db.get_bool("http_stream_as_live", False)
            configured_backends = db.get_setting("capture_backends", None)
            twitch_enabled = db.get_bool("twitch_enabled", False)
            self._inbox_enabled = db.get_bool("inbox_capture_enabled", False)
            self._clip_enabled = db.get_bool("live_clip_enabled", True)
            self._clip_seconds = int(db.get_int("live_clip_seconds", 5) or 5)
            self._clip_min_interval = float(db.get_float("live_clip_min_interval_sec", 10.0) or 10.0)
            self._clip_repeat_window = float(db.get_float("live_clip_repeat_window_sec", 60.0) or 60.0)
        except Exception:
            configured_prefixes = None
            http_as_live = False
            configured_backends = None
            twitch_enabled = False
            self._inbox_enabled = False
            self._clip_enabled = True
            self._clip_seconds = 5
            self._clip_min_interval = 10.0
            self._clip_repeat_window = 60.0

        live_prefixes = list(configured_prefixes or ["rtsp"])
        if http_as_live:
            live_prefixes.extend(["http://", "https://"])

        def _resolve_backends():

            default_names = ["CAP_MSMF"]
            names = configured_backends or default_names
            resolved = []
            for name in names:
                val = getattr(cv2, name, None)
                if val is not None:
                    resolved.append(val)
            return resolved or [cv2.CAP_ANY]

        def _resolve_source():
            if self._is_twitch and twitch_enabled in (True, 1, "1", "true", "True"):
                try:
                    import streamlink

                    session = streamlink.Streamlink()
                    streams = session.streams(str(self._raw_source))
                    if streams:
                        stream = streams.get("best") or next(iter(streams.values()))
                        url = stream.to_url() if hasattr(stream, "to_url") else getattr(stream, "url", None)
                        if url:
                            return url
                except Exception:
                    pass
            try:
                return int(self._raw_source) if str(self._raw_source).isdigit() else self._raw_source
            except (ValueError, AttributeError):
                return self._raw_source

        try:
            src = _resolve_source()
        except (ValueError, AttributeError):
            src = self._raw_source

        self._cap = None
        backends = _resolve_backends()
        for backend in backends:
            try:
                cap = cv2.VideoCapture(src, backend)
            except Exception:
                cap = None
            if cap and cap.isOpened():
                self._cap = cap
                break
            with contextlib.suppress(Exception):
                if cap:
                    cap.release()

        if self._cap is None or not self._cap.isOpened():
            try:
                self._cap = cv2.VideoCapture(src)
            except Exception:
                self._cap = None
            if not self._cap or not self._cap.isOpened():
                self.error_occurred.emit(self._camera_id, f"Cannot open camera: {self._source}")
                return

        _src_is_live = str(self._source).isdigit() or any(str(self._source).startswith(p) for p in live_prefixes)
        if _src_is_live:
            self._cap.set(cv2.CAP_PROP_FPS, self._fps_limit)

        detector = get_manager()
        pipeline = PipelineService(self._camera_id)

        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"infer-cam{self._camera_id}")
        pending_future: Future | None = None
        self._last_state: dict = {}

        display_delay = 1.0 / max(self._fps_limit, 1)
        self._last_fps_time = time.time()
        self._frame_count = 0

        is_file = not str(self._source).isdigit() and not any(str(self._source).startswith(p) for p in live_prefixes)
        consecutive_failures = 0
        _MAX_FAILURES = 5 if not is_file else 1
        frame_num = 0

        def _do_inference(infer_frame, cid, fw, fh, infer_scale=1.0):
            try:
                det = detector.process_frame(infer_frame, cid)
                if infer_scale < 0.999:
                    _inv = 1.0 / infer_scale
                    for _fi in det.get("faces", []):
                        _b = _fi.get("bbox")
                        if _b:
                            _fi["bbox"] = [int(_b[0] * _inv), int(_b[1] * _inv), int(_b[2] * _inv), int(_b[3] * _inv)]
                    for _oi in det.get("objects", []):
                        _b = _oi.get("bbox")
                        if _b:
                            _oi["bbox"] = [int(_b[0] * _inv), int(_b[1] * _inv), int(_b[2] * _inv), int(_b[3] * _inv)]
                primary, all_triggered = build_state(det, cid, fw, fh)
                primary["_triggered"] = all_triggered
                primary["_fw"] = fw
                primary["_fh"] = fh
                return primary
            except Exception:
                logging.getLogger(__name__).warning("_do_inference failed for camera %s", cid, exc_info=True)
                return {"_triggered": [], "_fw": fw, "_fh": fh}

        def _handle_inference_result(result, frame, fallback_fw, fallback_fh):
            triggered = result.pop("_triggered", [])
            infer_fw = result.pop("_fw", fallback_fw)
            infer_fh = result.pop("_fh", fallback_fh)
            result["_triggered"] = triggered
            result = pipeline.handle_result(
                result,
                frame,
                infer_fw=infer_fw,
                infer_fh=infer_fh,
                enable_inbox=self._inbox_enabled,
                enable_heatmap=get_service_manager().is_active("heatmap_generation"),
                inbox_context=self,
            )
            self._last_state = result
            if triggered and self._clip_enabled and self._clip_buffer:
                if self._should_save_clip(result):
                    clip_path = self._save_clip_from_buffer()
                    if clip_path:
                        try:
                            det = result.get("detections", {}) or {}
                            obj_types = [
                                k
                                for k, v in det.items()
                                if k not in ("identity", "gender") and v not in (False, 0, "unknown", None, "none")
                            ]
                            db.add_clip(
                                clip_path,
                                "live",
                                self._camera_id,
                                int(time.time()),
                                result.get("identity"),
                                result.get("triggered_rules") or [],
                                obj_types,
                            )
                        except Exception:
                            logging.getLogger(__name__).exception("Failed to record clip metadata for %s", clip_path)
                        self._last_clip_ts = time.time()

        def _submit_inference(frame, fw, fh):
            _INFER_DIM = 512
            _max_side = max(fw, fh)
            if _max_side > _INFER_DIM:
                _pre = _INFER_DIM / _max_side
                _infer_frame = cv2.resize(frame, (max(1, int(fw * _pre)), max(1, int(fh * _pre)))).copy()
            else:
                _infer_frame = frame.copy()
                _pre = 1.0
            return executor.submit(_do_inference, _infer_frame, self._camera_id, fw, fh, _pre)

        while self._running:
            t_start = time.time()
            ret, frame = self._cap.read()

            if not ret:
                consecutive_failures += 1
                if is_file:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    consecutive_failures = 0
                    time.sleep(0.05)
                    continue
                if consecutive_failures >= _MAX_FAILURES:
                    self._suppress_errors = True
                    try:
                        self.reconnecting.emit(self._camera_id)
                    except Exception:
                        pass
                    self._cap.release()
                    time.sleep(1.5)
                    try:
                        src = _resolve_source()
                    except Exception:
                        src = self._raw_source
                    self._cap = cv2.VideoCapture(src)
                    if not self._cap.isOpened():
                        self._suppress_errors = False
                        self.error_occurred.emit(self._camera_id, f"Cannot reconnect: {self._source}")
                        break
                    self._suppress_errors = False
                    consecutive_failures = 0
                else:
                    time.sleep(0.05)
                continue

            consecutive_failures = 0
            self._suppress_errors = False
            frame_num += 1
            fh, fw = frame.shape[:2]
            if self._clip_enabled:
                now_buf = time.time()
                self._clip_buffer.append((now_buf, frame.copy()))
                while self._clip_buffer and (now_buf - self._clip_buffer[0][0] > max(1, self._clip_seconds)):
                    self._clip_buffer.popleft()

            if pending_future is not None and pending_future.done():
                try:
                    result = pending_future.result(timeout=0)
                    _handle_inference_result(result, frame, fw, fh)
                except Exception:
                    logging.getLogger(__name__).exception("Inference result handling failed for camera %s", self._camera_id)
                pending_future = None

            if pending_future is None and (frame_num % self._infer_interval == 0):
                pending_future = _submit_inference(frame, fw, fh)

            self._frame_count += 1
            now = time.time()
            if now - self._last_fps_time >= 1.0:
                self._fps = self._frame_count / (now - self._last_fps_time)
                self._frame_count = 0
                self._last_fps_time = now
                self.fps_updated.emit(self._camera_id, self._fps)

            self.frame_ready.emit(self._camera_id, frame, dict(self._last_state))

            elapsed = time.time() - t_start
            sleep_time = display_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        executor.shutdown(wait=False)
        if self._cap:
            self._cap.release()

    def stop(self):
        self._running = False
        self.wait(3000)

    def clear_last_state(self):
        self._last_state = {}

    def _save_clip_from_buffer(self) -> str | None:
        try:
            os.makedirs("data/clips_live", exist_ok=True)
            frames = list(self._clip_buffer)
            if not frames:
                return None
            ts0, _ = frames[0]
            ts1, _ = frames[-1]
            duration = max(0.001, ts1 - ts0)
            fps = max(1.0, min(60.0, len(frames) / duration))
            sample = frames[0][1]
            h, w = sample.shape[:2]
            fname = os.path.join("data", "clips_live", f"clip_cam{self._camera_id}_{int(time.time())}.mp4")
            fourcc = cv2.VideoWriter.fourcc(*"mp4v")
            writer = cv2.VideoWriter(fname, fourcc, fps, (w, h))
            if not writer.isOpened():
                raise RuntimeError("VideoWriter failed to open (mp4v)")
            for _, f in frames:
                writer.write(f)
            writer.release()
            logging.getLogger(__name__).info("Live clip saved: %s", fname)
            return fname
        except Exception:
            logging.getLogger(__name__).exception("Live clip save failed for camera %s", self._camera_id)
            return None

    def _should_save_clip(self, result: dict) -> bool:
        now_ts = time.time()
        if now_ts - self._last_clip_ts < max(2.0, self._clip_min_interval):
            return False

        rules = result.get("triggered_rules") or []
        rules_key = tuple(sorted([str(r) for r in rules]))
        identity = result.get("identity") or "unknown"
        if identity == "unknown":
            identity_key = f"cam:{self._camera_id}"
        else:
            identity_key = f"id:{identity}"

        key = (identity_key, rules_key)
        last_ts = self._clip_recent.get(key)
        if last_ts and (now_ts - last_ts < self._clip_repeat_window):
            return False


        if len(self._clip_recent) > 200:
            cutoff = now_ts - max(self._clip_repeat_window, 120.0)
            self._clip_recent = {k: v for k, v in self._clip_recent.items() if v >= cutoff}

        self._clip_recent[key] = now_ts
        return True
