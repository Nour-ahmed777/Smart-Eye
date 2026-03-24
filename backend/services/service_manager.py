from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable

from backend.repository import db


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    start: Callable[[], None]
    stop: Callable[[], None]


class ServiceManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}
        self._specs: dict[str, ServiceSpec] = {}

    def register(self, spec: ServiceSpec) -> None:
        with self._lock:
            self._specs[spec.name] = spec
            self._counts.setdefault(spec.name, 0)

    def acquire(self, name: str) -> None:
        spec = self._specs.get(name)
        if not spec:
            return
        with self._lock:
            prev = self._counts.get(name, 0)
            self._counts[name] = prev + 1
        if prev == 0:
            self._maybe_start(spec)

    def release(self, name: str) -> None:
        spec = self._specs.get(name)
        if not spec:
            return
        with self._lock:
            prev = self._counts.get(name, 0)
            if prev <= 0:
                self._counts[name] = 0
                return
            self._counts[name] = prev - 1
            now = self._counts[name]
        if now == 0:
            self._maybe_stop(spec)

    def is_active(self, name: str) -> bool:
        with self._lock:
            return self._counts.get(name, 0) > 0

    def _maybe_start(self, spec: ServiceSpec) -> None:
        if spec.name == "live_cameras" and not db.get_bool("auto_pause_live_when_idle", False):
            return
        try:
            spec.start()
        except Exception:
            pass

    def _maybe_stop(self, spec: ServiceSpec) -> None:
        if spec.name == "live_cameras" and not db.get_bool("auto_pause_live_when_idle", False):
            return
        try:
            spec.stop()
        except Exception:
            pass


_instance: ServiceManager | None = None


def get_service_manager() -> ServiceManager:
    global _instance
    if _instance is None:
        _instance = ServiceManager()
        _register_defaults(_instance)
    return _instance


def _register_defaults(manager: ServiceManager) -> None:
    try:
        from backend.camera.camera_manager import get_camera_manager
    except Exception:
        get_camera_manager = None

    def _start_live():
        if get_camera_manager is None:
            return
        get_camera_manager().start_all_enabled()

    def _stop_live():
        if get_camera_manager is None:
            return
        get_camera_manager().stop_all()

    manager.register(ServiceSpec("live_cameras", _start_live, _stop_live))
    manager.register(ServiceSpec("heatmap_generation", lambda: None, lambda: None))
    manager.register(ServiceSpec("playback_detection", lambda: None, lambda: None))
