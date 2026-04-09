from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from backend.repository import db

_logger = logging.getLogger(__name__)

_THEME_CACHE: dict[str, object] = {"key": None, "payload": {}}
_THEME_DIR_REL = Path("data") / "themes"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _theme_dir() -> Path:
    return _repo_root() / _THEME_DIR_REL


def _legacy_theme_dir() -> Path:
    return _repo_root() / "frontend" / "themes"


def ensure_theme_dir() -> Path:
    path = _theme_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_get_theme_name() -> str:
    try:
        raw = db.get_setting("theme", "dark")
        return (str(raw).strip() or "dark").lower()
    except Exception:
        return "dark"


def _safe_get_theme_path_setting() -> str:
    try:
        raw = db.get_setting("theme_json_path", "")
        return str(raw or "").strip()
    except Exception:
        return ""


def _resolve_theme_file() -> Path | None:
    explicit = _safe_get_theme_path_setting()
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = _repo_root() / p
        if p.is_file():
            return p

    name = _safe_get_theme_name()
    if name.endswith(".json"):
        p = Path(name)
        if not p.is_absolute():
            p = _repo_root() / p
        if p.is_file():
            return p

    if name in ("", "dark"):
        return None

    candidate = _theme_dir() / f"{name}.json"
    if candidate.is_file():
        return candidate

    legacy = _legacy_theme_dir() / f"{name}.json"
    return legacy if legacy.is_file() else None


def _load_payload(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        _logger.warning("Failed to load theme json: %s", path, exc_info=True)
    return {}


def get_active_theme_payload() -> dict:
    # Cache key includes chosen theme name and explicit path so runtime reads are cheap.
    key = f"{_safe_get_theme_name()}|{_safe_get_theme_path_setting()}"
    if _THEME_CACHE.get("key") == key:
        cached = _THEME_CACHE.get("payload")
        return cached if isinstance(cached, dict) else {}

    path = _resolve_theme_file()
    payload = _load_payload(path)
    _THEME_CACHE["key"] = key
    _THEME_CACHE["payload"] = payload
    if path:
        _logger.info("Loaded theme json: %s", path)
    return payload


def invalidate_theme_cache() -> None:
    _THEME_CACHE["key"] = None
    _THEME_CACHE["payload"] = {}


def list_available_themes() -> list[str]:
    names: set[str] = set()
    for base in (_theme_dir(), _legacy_theme_dir()):
        if not base.exists():
            continue
        try:
            for p in base.glob("*.json"):
                stem = p.stem.strip().lower()
                if stem:
                    names.add(stem)
        except Exception:
            _logger.warning("Failed reading themes dir: %s", base, exc_info=True)

    names.discard("dark")
    return sorted(names)


def install_theme_json(source_path: str) -> tuple[str, str]:
    src = Path(str(source_path or "")).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Theme file not found: {src}")

    try:
        parsed = json.loads(src.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("Invalid JSON theme file") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Theme JSON must be an object")

    theme_name = str(parsed.get("name") or src.stem).strip().lower().replace(" ", "_")
    safe = "".join(ch for ch in theme_name if ch.isalnum() or ch in ("_", "-")) or "custom_theme"

    dst_dir = ensure_theme_dir()
    dst = dst_dir / f"{safe}.json"
    i = 2
    while dst.exists() and dst.resolve() != src:
        dst = dst_dir / f"{safe}_{i}.json"
        i += 1

    if dst.resolve() != src:
        shutil.copy2(src, dst)

    rel = _THEME_DIR_REL / dst.name
    return dst.stem.lower(), rel.as_posix()
