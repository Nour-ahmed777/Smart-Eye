import threading
import time

from backend.repository import db

_ZONE_CACHE: dict[int, tuple[float, list[dict]]] = {}
_ZONE_CACHE_LOCK = threading.Lock()
_ZONE_CACHE_TTL_SEC = 2.0


def invalidate_zone_cache(camera_id=None):
    with _ZONE_CACHE_LOCK:
        if camera_id is None:
            _ZONE_CACHE.clear()
        else:
            _ZONE_CACHE.pop(int(camera_id), None)


def _get_zones_cached(camera_id):
    cid = int(camera_id)
    now = time.time()
    with _ZONE_CACHE_LOCK:
        entry = _ZONE_CACHE.get(cid)
        if entry and (now - entry[0]) < _ZONE_CACHE_TTL_SEC:
            return entry[1]
    try:
        zones = db.get_zones(camera_id=cid, enabled_only=True)
    except Exception:
        zones = []
    with _ZONE_CACHE_LOCK:
        _ZONE_CACHE[cid] = (now, zones)
    return zones


def filter_detections_by_zone(detection_results, camera_id, frame_w, frame_h):
    zones = _get_zones_cached(camera_id)
    if not zones:
        return [{"zone": None, "results": detection_results}]

    def _center_in_zone(bbox, zone):
        bx1, by1, bx2, by2 = bbox
        cx = (bx1 + bx2) / 2
        cy = (by1 + by2) / 2
        zx1 = zone["x1"] * frame_w
        zy1 = zone["y1"] * frame_h
        zx2 = zone["x2"] * frame_w
        zy2 = zone["y2"] * frame_h
        return zx1 <= cx <= zx2 and zy1 <= cy <= zy2

    def _split_by_zone(entries):
        in_zone = {z["id"]: [] for z in zones}
        unzoned = []
        for ent in entries:
            bbox = ent.get("bbox")
            if not bbox:
                continue
            matched = False
            for z in zones:
                if _center_in_zone(bbox, z):
                    in_zone[z["id"]].append(ent)
                    matched = True
            if not matched:
                unzoned.append(ent)
        return in_zone, unzoned

    objects_by_zone, unzoned_objects = _split_by_zone(detection_results.get("objects", []))
    faces_by_zone, unzoned_faces = _split_by_zone(detection_results.get("faces", []))

    zone_results = []
    for zone in zones:
        zid = zone["id"]
        zone_result = {
            "zone": zone,
            "results": {
                "faces": faces_by_zone.get(zid, []),
                "objects": objects_by_zone.get(zid, []),
                "face_time_ms": detection_results.get("face_time_ms", 0),
                "object_time_ms": detection_results.get("object_time_ms", 0),
            },
        }
        zone_results.append(zone_result)

    if unzoned_faces or unzoned_objects:
        zone_results.append(
            {
                "zone": None,
                "results": {
                    "faces": unzoned_faces,
                    "objects": unzoned_objects,
                    "face_time_ms": 0,
                    "object_time_ms": 0,
                },
            }
        )
    return zone_results
