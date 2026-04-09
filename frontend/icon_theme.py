from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtCore import Qt

from frontend.theme_runtime import get_active_theme_payload


_DEFAULT_LIGHT_ICON = "#2f3d52"
_DEFAULT_DARK_ICON = "#eaf4ff"


def _icon_cfg() -> dict:
    payload = get_active_theme_payload() or {}
    cfg = payload.get("icons", {})
    return cfg if isinstance(cfg, dict) else {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _cache_dir() -> Path:
    p = _repo_root() / "data" / "cache" / "theme_icons"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _parse_color(s: str, fallback: str) -> QColor:
    c = QColor(str(s or ""))
    if not c.isValid():
        c = QColor(fallback)
    return c


def _luminance(c: QColor) -> float:
    return (0.2126 * c.red()) + (0.7152 * c.green()) + (0.0722 * c.blue())


def _theme_bg_luminance() -> float:
    payload = get_active_theme_payload() or {}
    colors = payload.get("colors", payload)
    if isinstance(colors, dict):
        c = _parse_color(str(colors.get("_BG_SURFACE", "#ffffff")), "#ffffff")
        return _luminance(c)
    return _luminance(QColor("#ffffff"))


def _pixmap_luminance(pm: QPixmap) -> float:
    img = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    w = img.width()
    h = img.height()
    if w <= 0 or h <= 0:
        return 128.0

    total = 0.0
    count = 0
    for y in range(h):
        for x in range(w):
            col = img.pixelColor(x, y)
            if col.alpha() <= 8:
                continue
            total += _luminance(col)
            count += 1
    if count <= 0:
        return 128.0
    return total / count


def _invert_image(img: QImage) -> QImage:
    out = img.convertToFormat(QImage.Format.Format_ARGB32)
    out.invertPixels(QImage.InvertMode.InvertRgb)
    return out


def _tint_pixmap(pm: QPixmap, color: QColor) -> QPixmap:
    if pm.isNull():
        return pm
    out = QPixmap(pm.size())
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), color)
    p.end()
    return out


def _tint_image(img: QImage, color: QColor) -> QImage:
    if img.isNull():
        return img
    out = img.convertToFormat(QImage.Format.Format_ARGB32)
    p = QPainter(out)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(out.rect(), color)
    p.end()
    return out


def _image_luminance(img: QImage) -> float:
    conv = img.convertToFormat(QImage.Format.Format_ARGB32)
    w = conv.width()
    h = conv.height()
    if w <= 0 or h <= 0:
        return 128.0

    total = 0.0
    count = 0
    for y in range(h):
        for x in range(w):
            col = conv.pixelColor(x, y)
            if col.alpha() <= 8:
                continue
            total += _luminance(col)
            count += 1
    if count <= 0:
        return 128.0
    return total / count


def themed_existing_pixmap(pm: QPixmap) -> QPixmap:
    if pm.isNull():
        return pm

    cfg = _icon_cfg()
    enabled = bool(cfg.get("enabled", False))
    if not enabled:
        return pm

    mode = str(cfg.get("mode", "tint")).strip().lower()
    if mode == "invert":
        inv = _invert_image(pm.toImage())
        return QPixmap.fromImage(inv)

    if mode == "auto":
        bg_l = _theme_bg_luminance()
        icon_l = _pixmap_luminance(pm)
        if abs(bg_l - icon_l) >= 95.0:
            return pm
        target = _DEFAULT_LIGHT_ICON if bg_l >= 128.0 else _DEFAULT_DARK_ICON
        color = _parse_color(str(cfg.get("color", target)), target)
        return _tint_pixmap(pm, color)

    color = _parse_color(str(cfg.get("color", _DEFAULT_LIGHT_ICON)), _DEFAULT_LIGHT_ICON)
    return _tint_pixmap(pm, color)


def themed_icon_pixmap(path: str, width: int, height: int) -> QPixmap:
    pm = QPixmap(path)
    if pm.isNull():
        return pm

    scaled = pm.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    return themed_existing_pixmap(scaled)


def themed_icon_path(path: str) -> str:
    img = QImage(path)
    if img.isNull():
        return path

    cfg = _icon_cfg()
    enabled = bool(cfg.get("enabled", False))
    if not enabled:
        return path

    mode = str(cfg.get("mode", "tint")).strip().lower()
    if mode == "invert":
        themed_img = _invert_image(img)
    elif mode == "auto":
        bg_l = _theme_bg_luminance()
        icon_l = _image_luminance(img)
        if abs(bg_l - icon_l) >= 95.0:
            themed_img = img
        else:
            target = _DEFAULT_LIGHT_ICON if bg_l >= 128.0 else _DEFAULT_DARK_ICON
            color = _parse_color(str(cfg.get("color", target)), target)
            themed_img = _tint_image(img, color)
    else:
        color = _parse_color(str(cfg.get("color", _DEFAULT_LIGHT_ICON)), _DEFAULT_LIGHT_ICON)
        themed_img = _tint_image(img, color)

    payload = get_active_theme_payload() or {}
    colors = payload.get("colors", payload) if isinstance(payload, dict) else {}
    bg = str(colors.get("_BG_SURFACE", "#ffffff")) if isinstance(colors, dict) else "#ffffff"
    sig_src = f"{path}|{cfg.get('enabled')}|{cfg.get('mode')}|{cfg.get('color')}|{bg}"
    sig = hashlib.md5(sig_src.encode("utf-8")).hexdigest()[:12]

    src = Path(path)
    out = _cache_dir() / f"{src.stem}_{sig}.png"
    if not out.exists():
        themed_img.save(str(out), "PNG")
    return out.as_posix()
