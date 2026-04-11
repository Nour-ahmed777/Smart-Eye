import json
import logging
import os
import queue
import threading
import time
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from backend.notifications.email_notifier import send_email_alert
from backend.notifications.webhook_notifier import send_webhook
from backend.repository import db
from utils import config
from utils.image_utils import save_snapshot


class AlarmHandler:
    def __init__(self, data_dir="data"):
        self._data_dir = data_dir
        self._log = logging.getLogger(__name__)

        self._alarm = QSoundEffect()
        self._alarm.setLoopCount(-2)
        self._alarm.setVolume(0.8)
        self._alarm_playing = False
        self._last_trigger_ts = 0.0
        self._alarm_grace_seconds = 0.35
        self._last_action_times = {}
        self._last_log_ts: dict = {}

        self._task_queue: queue.Queue = queue.Queue(maxsize=512)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._worker_loop, name="alarm-worker", daemon=True)
        self._worker.start()

    def close(self):
        self._stop_event.set()
        try:
            self._task_queue.put_nowait(None)
        except Exception:
            pass
        try:
            if self._worker.is_alive():
                self._worker.join(timeout=1.5)
        except Exception:
            pass

    def _enqueue(self, task):
        if self._stop_event.is_set():
            return
        try:
            self._task_queue.put_nowait(task)
        except queue.Full:

            try:
                self._task_queue.get_nowait()
            except Exception:
                pass
            try:
                self._task_queue.put_nowait(task)
            except Exception:
                self._log.warning("Alarm worker queue full; dropping task")

    def _worker_loop(self):
        while not self._stop_event.is_set():
            try:
                task = self._task_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if task is None:
                break
            try:
                kind = task.get("kind")
                if kind == "action":
                    self._execute_action(task["action"], task["state"], task.get("frame"))
                elif kind == "log":
                    self._write_detection_log(task["rule"], task["level"], task["state"], task.get("frame"))
            except Exception:
                self._log.exception("Alarm worker task failed")

    def handle_alarms(self, triggered_rules, escalation_levels, state, frame=None):
        now = time.time()
        should_play_alarm = False
        executed = []
        for rule in triggered_rules:
            if not rule.get("enabled", 1):
                continue
            rule_id = rule["id"]
            level = escalation_levels.get(rule_id, 0)
            if level <= 0:
                continue
            actions = db.get_alarm_actions(rule_id=rule_id, escalation_level=level)
            for action in actions:
                if action.get("action_type") == "sound":
                    should_play_alarm = True
                cooldown = action.get("cooldown_sec", 10)
                key = (rule_id, action["id"])
                last = self._last_action_times.get(key, 0)
                if now - last < cooldown:
                    continue
                action_frame = frame.copy() if frame is not None else None
                self._enqueue({"kind": "action", "action": dict(action), "state": dict(state), "frame": action_frame})
                self._last_action_times[key] = now
                executed.append(action)

            log_key = (rule_id, state.get("camera_id"), state.get("identity"))
            if now - self._last_log_ts.get(log_key, 0) < 30.0:
                continue
            self._last_log_ts[log_key] = now
            log_frame = frame.copy() if frame is not None and config.snapshot_on_alarm() else None
            self._enqueue({"kind": "log", "rule": dict(rule), "level": level, "state": dict(state), "frame": log_frame})

        if should_play_alarm:
            self._last_trigger_ts = now
            if not self._alarm_playing:
                self._start_alarm()
        else:
            if self._alarm_playing and (now - self._last_trigger_ts > self._alarm_grace_seconds):
                self._stop_alarm()

        return executed

    def _write_detection_log(self, rule, level, state, frame):
        snapshot_path = ""
        if frame is not None:
            snapshot_path = save_snapshot(
                frame,
                Path(self._data_dir) / "snapshots",
            )
        db.add_detection_log(
            camera_id=state.get("camera_id"),
            zone_id=state.get("zone_id"),
            identity=state.get("identity"),
            face_confidence=state.get("face_confidence", 0),
            detections=state.get("detections", {}),
            rules_triggered=[rule.get("name")],
            alarm_level=level,
            snapshot_path=snapshot_path,
        )

    def _execute_action(self, action, state, frame):
        atype = action["action_type"]
        avalue = action.get("action_value", "")
        if atype == "email":
            self._send_email(avalue, state)
        elif atype == "webhook":
            self._send_webhook(avalue, state)
        return False

    def _start_alarm(self):
        if self._alarm_playing:
            return
        sound_path = Path("frontend/assets/sounds/alarm_level_1.wav").resolve()
        if not sound_path.is_file():
            self._log.warning("Alarm sound not found: %s", sound_path)
            return
        if os.name == "nt":
            try:
                import winsound

                winsound.PlaySound(
                    str(sound_path),
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
                )
                self._alarm_playing = True
                self._log.info("Alarm STARTED (winsound) -> %s", sound_path)
                return
            except Exception:
                self._log.exception("winsound start failed; falling back to QSoundEffect")
        if self._alarm is None:
            return
        self._alarm.setSource(QUrl.fromLocalFile(str(sound_path)))
        self._alarm.play()
        self._alarm_playing = True
        self._log.info("Alarm STARTED (qt) -> %s", sound_path)

    def _stop_alarm(self):
        if not self._alarm_playing:
            return
        if os.name == "nt":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                self._log.exception("winsound stop failed")
        if self._alarm is None:
            self._alarm_playing = False
            return
        self._alarm.stop()
        self._alarm_playing = False
        self._log.info("Alarm STOPPED")

    def _send_email(self, address, state):
        try:
            subject = f"SmartEye Alert: {state.get('identity', 'Unknown')}"
            body = json.dumps(state.get("detections", {}), indent=2)
            send_email_alert(address, subject, body)
        except Exception:
            self._log.exception("Email send failed")

    def _send_webhook(self, url, state):
        try:
            payload = {
                "identity": state.get("identity"),
                "detections": state.get("detections", {}),
                "camera_id": state.get("camera_id"),
                "zone": state.get("zone"),
                "timestamp": time.time(),
            }
            send_webhook(url, payload)
        except Exception:
            self._log.exception("Webhook send failed")


_instance = None


def get_handler(data_dir="data"):
    global _instance
    if _instance is None:
        try:
            _instance = AlarmHandler(data_dir)
        except Exception:
            logging.getLogger(__name__).exception("Failed to initialize AlarmHandler; using silent fallback")
            _instance = AlarmHandler.__new__(AlarmHandler)
            _instance._data_dir = data_dir
            _instance._log = logging.getLogger(__name__)
            _instance._alarm = None
            _instance._alarm_playing = False
            _instance._last_trigger_ts = 0.0
            _instance._alarm_grace_seconds = 2.0
            _instance._last_action_times = {}
            _instance._last_log_ts = {}
            _instance._task_queue = queue.Queue(maxsize=16)
            _instance._worker = threading.Thread(target=lambda: None, daemon=True)
            _instance._stop_event = threading.Event()
    return _instance


def stop_all_sounds():
    handler = get_handler()
    with_logging = getattr(handler, "_stop_alarm", None)
    if callable(with_logging):
        handler._stop_alarm()
    close_fn = getattr(handler, "close", None)
    if callable(close_fn):
        close_fn()
