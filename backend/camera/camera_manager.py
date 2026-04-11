import contextlib
import logging
import threading

from backend.camera.camera_thread import CameraThread
from backend.repository import db


class CameraManager:
    def __init__(self):
        self._threads = {}
        self._lock = threading.Lock()

    def start_camera(self, camera_id):
        with self._lock:
            if camera_id in self._threads and self._threads[camera_id].isRunning():
                return
        cam = db.get_camera(camera_id)
        if not cam or not cam.get("enabled"):
            return
        infer_interval = max(1, int(db.get_int("detection_interval", 1) or 1))
        thread = CameraThread(
            camera_id=cam["id"],
            source=cam["source"],
            fps_limit=cam.get("fps_limit", 30),
        )
        try:
            thread.error_occurred.connect(
                lambda cid, msg: logging.getLogger(__name__).warning("camera_thread error cid=%s msg=%s", cid, msg)
            )
            thread.reconnecting.connect(lambda cid: logging.getLogger(__name__).info("camera_thread reconnecting cid=%s", cid))
        except Exception:
            pass
        thread.set_inference_interval(infer_interval)
        with self._lock:
            self._threads[camera_id] = thread
        thread.start()

    def stop_camera(self, camera_id):
        with self._lock:
            thread = self._threads.pop(camera_id, None)
        if thread:
            thread.stop()
        try:
            from backend.pipeline.detector_manager import get_manager

            get_manager().clear_camera_state(camera_id)
        except Exception:
            pass

    def stop_all(self):
        with self._lock:
            ids = list(self._threads.keys())
        for cid in ids:
            self.stop_camera(cid)
        try:
            from backend.pipeline.alarm_handler import stop_all_sounds

            stop_all_sounds()
        except Exception:
            pass

    def start_all_enabled(self):
        cameras = db.get_cameras(enabled_only=True)
        for cam in cameras:
            self.start_camera(cam["id"])

    def get_thread(self, camera_id):
        with self._lock:
            return self._threads.get(camera_id)

    def get_active_ids(self):
        with self._lock:
            return list(self._threads.keys())

    def clear_all_states(self):
        with self._lock:
            threads = list(self._threads.values())
        for t in threads:
            with contextlib.suppress(Exception):
                t.clear_last_state()
        try:
            from backend.pipeline.detector_manager import get_manager

            get_manager().clear_camera_state()
        except Exception:
            pass


_instance = None


def get_camera_manager():
    global _instance
    if _instance is None:
        _instance = CameraManager()
    return _instance
