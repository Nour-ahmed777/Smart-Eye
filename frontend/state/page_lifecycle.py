from __future__ import annotations

from typing import Protocol


class PageLifecycle(Protocol):
    def on_activated(self) -> None: ...

    def on_deactivated(self) -> None: ...

    def on_unload(self) -> None: ...
