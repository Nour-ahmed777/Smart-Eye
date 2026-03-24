from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from frontend.pages.analytics import AnalyticsPage
from frontend.pages.camera_manager import CameraManagerPage
from frontend.pages.dashboard import DashboardPage
from frontend.pages.face_manager import FaceManagerPage
from frontend.pages.logs import LogsViewerPage
from frontend.pages.models import ModelsPage
from frontend.pages.notifications_manager import NotificationsConfigPage
from frontend.pages.playback import PlaybackPage
from frontend.pages.rules_manager import RulesManagerPage
from frontend.pages.settings import SettingsPage
from frontend.services.rules_service import RulesService


class UnloadPolicy:
    KEEP = "keep"
    IDLE = "idle"
    DESTROY = "destroy"


@dataclass(frozen=True)
class PageSpec:
    key: str
    factory: Callable[[], object | None]
    unload_policy: str
    services: tuple[str, ...] = ()
    preload: bool = False


def _page_specs(rules_service: RulesService) -> dict[str, PageSpec]:
    return {
        "dashboard": PageSpec(
            key="dashboard",
            factory=DashboardPage,
            unload_policy=UnloadPolicy.DESTROY,
            services=("live_cameras",),
            preload=True,
        ),
        "detectors": PageSpec(
            key="detectors",
            factory=CameraManagerPage,
            unload_policy=UnloadPolicy.DESTROY,
            services=("live_cameras",),
        ),
        "rules": PageSpec(
            key="rules",
            factory=lambda: RulesManagerPage(rules_service=rules_service),
            unload_policy=UnloadPolicy.KEEP,
        ),
        "models": PageSpec(
            key="models",
            factory=ModelsPage,
            unload_policy=UnloadPolicy.DESTROY,
        ),
        "faces": PageSpec(
            key="faces",
            factory=FaceManagerPage,
            unload_policy=UnloadPolicy.DESTROY,
        ),
        "analytics": PageSpec(
            key="analytics",
            factory=AnalyticsPage,
            unload_policy=UnloadPolicy.IDLE,
            services=("heatmap_generation",),
        ),
        "logs": PageSpec(
            key="logs",
            factory=LogsViewerPage,
            unload_policy=UnloadPolicy.KEEP,
        ),
        "playback": PageSpec(
            key="playback",
            factory=PlaybackPage,
            unload_policy=UnloadPolicy.DESTROY,
            services=("playback_detection",),
        ),
        "notifications": PageSpec(
            key="notifications",
            factory=NotificationsConfigPage,
            unload_policy=UnloadPolicy.KEEP,
        ),
        "settings": PageSpec(
            key="settings",
            factory=SettingsPage,
            unload_policy=UnloadPolicy.KEEP,
            preload=True,
        ),
    }


def create_page(key: str, rules_service: RulesService) -> object | None:
    spec = _page_specs(rules_service).get(key)
    return spec.factory() if spec else None


def build_pages(preload_fn: Callable[[str], bool], rules_service: RulesService) -> dict[str, object | None]:
    specs = _page_specs(rules_service)

    def _preload(key: str, always: bool = False) -> bool:
        return always or preload_fn(key)

    pages: dict[str, object | None] = {}
    for key, spec in specs.items():
        should_preload = _preload(key, spec.preload)
        pages[key] = spec.factory() if should_preload else None
    return pages


def get_page_specs(rules_service: RulesService) -> dict[str, PageSpec]:
    return _page_specs(rules_service)
