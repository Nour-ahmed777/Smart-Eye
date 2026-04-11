import threading
import time


class EscalationManager:
    def __init__(self):
        # Keyed by (camera_id, rule_id) to isolate escalation state per camera/session.
        self._active_violations = {}
        self._lock = threading.Lock()

    def update(self, camera_id, triggered_rules):
        now = time.time()
        cam = int(camera_id) if camera_id is not None else -1
        current_ids = {int(r["id"]) for r in triggered_rules}
        with self._lock:
            expired = [
                key for key in self._active_violations if key[0] == cam and key[1] not in current_ids
            ]
            for key in expired:
                del self._active_violations[key]
            for rule in triggered_rules:
                rid = int(rule["id"])
                key = (cam, rid)
                if key not in self._active_violations:
                    self._active_violations[key] = {
                        "start_time": now,
                        "rule": rule,
                    }

    def get_escalation_levels(self, camera_id, triggered_rules):
        now = time.time()
        cam = int(camera_id) if camera_id is not None else -1
        levels = {}
        from backend.repository import db

        for rule in triggered_rules:
            rid = int(rule["id"])
            with self._lock:
                active = self._active_violations.get((cam, rid))
            if not active:
                levels[rid] = 0
                continue
            elapsed = now - active["start_time"]
            actions = db.get_alarm_actions(rule_id=rid)
            level = 0
            for action in sorted(actions, key=lambda a: a["escalation_level"]):
                if elapsed >= action.get("trigger_after_sec", 0):
                    level = action["escalation_level"]
            levels[rid] = level
        return levels

    def get_active_violations(self, camera_id):
        now = time.time()
        cam = int(camera_id) if camera_id is not None else -1
        result = []
        from backend.repository import db

        with self._lock:
            items = [(key, info) for key, info in self._active_violations.items() if key[0] == cam]
        for (_cam, rid), info in items:
            level = self.get_escalation_levels(cam, [info["rule"]]).get(rid, 0)

            if level <= 0:
                continue
            # Only surface "Active Alarms" when the current level explicitly includes popup.
            actions = db.get_alarm_actions(rule_id=rid, escalation_level=level)
            has_popup = any(str(a.get("action_type") or "").strip().lower() == "popup" for a in actions)
            if not has_popup:
                continue
            result.append(
                {
                    "rule_id": rid,
                    "rule_name": info["rule"].get("name", ""),
                    "duration": now - info["start_time"],
                    "level": level,
                }
            )
        return result

    def clear(self, camera_id=None):
        with self._lock:
            if camera_id is None:
                self._active_violations.clear()
                return
            cam = int(camera_id)
            for key in [k for k in self._active_violations if k[0] == cam]:
                self._active_violations.pop(key, None)


_instance = None


def get_escalation_manager():
    global _instance
    if _instance is None:
        _instance = EscalationManager()
    return _instance
