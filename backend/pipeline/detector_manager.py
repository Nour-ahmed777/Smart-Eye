import contextlib
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import cv2

from backend.repository import db
from backend.models import model_loader
from utils import config

logger = logging.getLogger(__name__)

_MAX_INFER_DIM = 512


_GHOST_TTL = 0.35
_MAX_GHOST_V = 28.0


def _scale_frame(frame, max_dim=_MAX_INFER_DIM):
    h, w = frame.shape[:2]
    largest = max(h, w)
    if largest <= max_dim:
        return frame, 1.0
    scale = max_dim / largest
    return cv2.resize(frame, (int(w * scale), int(h * scale))), scale


def _scale_bbox_up(bbox, scale):
    if scale == 1.0:
        return bbox
    s = 1.0 / scale
    return [int(bbox[0] * s), int(bbox[1] * s), int(bbox[2] * s), int(bbox[3] * s)]


def _iou(a, b):
    try:
        if not a or not b:
            return 0.0
        xA, yA = max(a[0], b[0]), max(a[1], b[1])
        xB, yB = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, xB - xA) * max(0, yB - yA)
        areaA = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
        areaB = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
        denom = float(areaA + areaB - inter)
        return inter / denom if denom > 0 else 0.0
    except Exception:
        return 0.0


def _smooth_bbox(prev, curr, alpha=0.6):
    try:
        if not prev or not curr:
            return curr

        px1, py1, px2, py2 = [float(x) for x in prev]

        cx1, cy1, cx2, cy2 = [float(x) for x in curr]

        pcx = (px1 + px2) / 2.0
        pcy = (py1 + py2) / 2.0
        pw = max(1.0, px2 - px1)
        ph = max(1.0, py2 - py1)

        ccx = (cx1 + cx2) / 2.0
        ccy = (cy1 + cy2) / 2.0
        cw = max(1.0, cx2 - cx1)
        ch = max(1.0, cy2 - cy1)

        alpha_pos = float(alpha)

        alpha_size = min(0.95, alpha_pos + 0.2)

        ncx = alpha_pos * ccx + (1.0 - alpha_pos) * pcx
        ncy = alpha_pos * ccy + (1.0 - alpha_pos) * pcy

        nw = alpha_size * cw + (1.0 - alpha_size) * pw
        nh = alpha_size * ch + (1.0 - alpha_size) * ph

        max_scale_change = 0.25
        min_w = pw * (1.0 - max_scale_change)
        max_w = pw * (1.0 + max_scale_change)
        min_h = ph * (1.0 - max_scale_change)
        max_h = ph * (1.0 + max_scale_change)
        nw = max(min_w, min(max_w, nw))
        nh = max(min_h, min(max_h, nh))

        nx1 = int(ncx - nw / 2.0)
        ny1 = int(ncy - nh / 2.0)
        nx2 = int(ncx + nw / 2.0)
        ny2 = int(ncy + nh / 2.0)

        return [nx1, ny1, nx2, ny2]
    except Exception:
        return curr


class DetectorManager:
    def __init__(self):
        self._face_model = None
        self._plugin_models = {}
        self._plugin_models_lock = threading.Lock()
        self._camera_plugins = {}
        self._initialized = False
        self._init_lock = threading.Lock()
        self._camera_plugins_lock = threading.Lock()
        self._camera_states = {}
        self._camera_states_lock = threading.Lock()
        self._camera_threshold_cache = {}
        self._camera_threshold_cache_lock = threading.Lock()
        self._camera_settings_cache = {}
        self._camera_settings_cache_lock = threading.Lock()

        self._cam_plugin_classes_cache = {}
        self._cam_plugin_classes_cache_lock = threading.Lock()

        self._ghost_settings_cache: dict = {}
        self._ghost_settings_ts: float = 0.0

        try:
            self._identify_cooldown = int(config.get("identify_cooldown_frames", 6) or 6)
        except Exception:
            self._identify_cooldown = 6

        try:
            max_threads = int(config.get("max_threads", None) or 0)
        except Exception:
            max_threads = 0

        if max_threads > 0:
            workers = max(1, max_threads)
        else:
            workers = max(1, min(2, (os.cpu_count() or 2) // 2))

        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="det-worker")

    class _CameraState:
        def __init__(self):
            self.frame_counter = 0
            self.counter_lock = threading.Lock()
            self.trackers = []
            self.trackers_lock = threading.Lock()
            self.smoothing_state = {"faces": [], "objects": []}
            self.smoothing_lock = threading.Lock()
            self.ghost_store = {"faces": [], "objects": []}

    def _get_camera_state(self, camera_id):
        with self._camera_states_lock:
            state = self._camera_states.get(camera_id)
            if state is None:
                state = self._CameraState()
                self._camera_states[camera_id] = state
            return state

    def clear_camera_state(self, camera_id=None):
        with self._camera_states_lock:
            if camera_id is None:
                self._camera_states.clear()
            else:
                self._camera_states.pop(camera_id, None)

    def initialize(self):
        with self._init_lock:
            if self._initialized:
                return
            try:
                self._face_model = model_loader.load_face_model_async()
            except Exception:
                logger.warning("Failed to load face model", exc_info=True)
                self._face_model = None
            self._reload_plugins()
            self._initialized = True

    def ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def reload(self):
        with self._init_lock:
            self._initialized = False
        config.invalidate_cache()
        self.initialize()

    def _reload_plugins(self):
        try:
            enabled_rows = db.get_plugins(enabled_only=True)
        except Exception:
            logger.warning("Failed to fetch enabled plugins", exc_info=True)
            return

        assigned_enabled = set()
        for p in enabled_rows:
            try:
                if db.get_plugin_cameras(p["id"]):
                    assigned_enabled.add(p["id"])
            except Exception:
                logger.debug("Failed to check cameras for plugin %s", p.get("id"), exc_info=True)

        try:
            loaded = set(model_loader.get_loaded_plugins().keys())
            for pid in loaded - assigned_enabled:
                try:
                    model_loader.unload_plugin(pid)
                except Exception:
                    logger.debug("Failed to unload plugin %s", pid, exc_info=True)
        except Exception:
            logger.debug("Failed to get loaded plugins", exc_info=True)

        with self._plugin_models_lock:
            self._plugin_models.clear()
            for p in enabled_rows:
                pid = p.get("id")
                if pid not in assigned_enabled:
                    continue
                try:
                    model = model_loader.load_plugin(p)
                    if model is not None:
                        self._plugin_models[pid] = {
                            "model": model,
                            "info": p,
                            "classes": db.get_plugin_classes(pid),
                        }
                except Exception:
                    logger.exception("Failed to load plugin %s (%s)", pid, p.get("name"))

    def get_plugins_for_camera(self, camera_id):
        with self._camera_plugins_lock:
            if camera_id not in self._camera_plugins:
                cp = db.get_camera_plugins(camera_id)
                if cp:
                    self._camera_plugins[camera_id] = [p["id"] for p in cp]
                else:
                    with self._plugin_models_lock:
                        self._camera_plugins[camera_id] = list(self._plugin_models.keys())
            return list(self._camera_plugins[camera_id])

    def invalidate_camera_cache(self, camera_id=None):
        with self._camera_plugins_lock:
            if camera_id:
                self._camera_plugins.pop(camera_id, None)
            else:
                self._camera_plugins.clear()

    def _make_tracker(self):
        _factories = []
        for _names in (
            ("legacy", "TrackerCSRT_create"),
            (None, "TrackerCSRT_create"),
            ("legacy", "TrackerKCF_create"),
            (None, "TrackerKCF_create"),
        ):
            try:
                module, attr = _names
                if module:
                    _factories.append(getattr(getattr(cv2, module), attr))
                else:
                    _factories.append(getattr(cv2, attr))
            except AttributeError:
                pass
        for factory in _factories:
            try:
                return factory()
            except Exception:
                continue
        return None

    def _read_frame_settings(self):
        try:
            detection_interval = int(config.get("detection_interval", 2) or 2)
        except Exception:
            detection_interval = 2

        aggressive_mode = False
        for key in ("aggressive_perf_mode", "smoothing_enabled", "experimental_smoothing"):
            val = config.get(key, None)
            if val is not None:
                if isinstance(val, str):
                    aggressive_mode = val.strip().lower() in ("1", "true", "yes")
                else:
                    aggressive_mode = bool(val)
                break

        if aggressive_mode:
            try:
                detection_interval = int(config.get("aggressive_detection_interval", 5) or 5)
            except Exception:
                detection_interval = max(detection_interval, 5)

        try:
            max_identify = int(config.get("aggressive_max_identify_per_frame", 2) or 2)
        except Exception:
            max_identify = 2

        try:
            max_trackers = int(config.get("max_trackers_per_cam", 32) or 32)
        except Exception:
            max_trackers = 32

        return detection_interval, aggressive_mode, max_identify, max_trackers

    def _scale_for_mode(self, frame, aggressive_mode):
        if aggressive_mode:
            try:
                max_dim = int(config.get("aggressive_max_infer_dim", 480) or 480)
            except Exception:
                max_dim = 480
            return _scale_frame(frame, max_dim=max_dim)
        return _scale_frame(frame, max_dim=_MAX_INFER_DIM)

    def _run_face_detection(self, camera_id, small, scale):
        t0 = time.time()
        faces = self._face_model.detect_faces(small)
        results = []
        for face in faces:
            face["bbox"] = _scale_bbox_up(face["bbox"], scale)
            results.append(
                {
                    "bbox": face["bbox"],
                    "det_score": face.get("det_score", 1.0),
                    "identity": None,
                    "confidence": None,
                    "embedding": face.get("embedding"),
                    "liveness": None,
                    "gender": face.get("gender", "unknown"),
                    "gender_confidence": face.get("gender_confidence", 0.0),
                }
            )
        return results, (time.time() - t0) * 1000

    def _run_plugin(self, pid, small, scale, camera_id):
        with self._plugin_models_lock:
            entry = self._plugin_models.get(pid)
        if entry is None:
            return [], 0.0
        model = entry["model"]
        t0 = time.time()
        detections = model.detect(small) or []

        logger.debug("Plugin %s raw detections: %d", pid, len(detections))

        global_classes = {int(c.get("class_index")): c for c in entry.get("classes", [])}

        cam_over = []
        try:
            cam_over = self._get_camera_plugin_classes_cached(camera_id, pid) or []
        except Exception:
            cam_over = []
        overrides = {int(r.get("class_index")): r for r in cam_over}

        plugin_conf = entry.get("info", {}).get("confidence", 0.5)
        filtered = []

        for det in detections:
            try:
                det["bbox"] = _scale_bbox_up(det["bbox"], scale)
            except Exception:
                logger.debug("Skipping detection with bad bbox in plugin %s", pid, exc_info=True)
                continue

            cls = det.get("class") if det.get("class") is not None else det.get("class_id")
            try:
                cls = int(cls)
            except Exception:
                continue

            effective = dict(global_classes.get(cls, {}))

            if cls in overrides:
                over = overrides[cls]
                try:
                    effective["enabled"] = int(over.get("enabled", effective.get("enabled", 1)))
                except Exception:
                    effective["enabled"] = effective.get("enabled", 1)
                if over.get("confidence") is not None:
                    effective["confidence"] = over.get("confidence")

            if effective.get("enabled", 1) in (0, "0", False):
                continue

            class_conf = effective.get("confidence")
            if class_conf is None:
                try:
                    class_conf = float(entry.get("info", {}).get("confidence", plugin_conf))
                except Exception:
                    class_conf = plugin_conf

            if det.get("confidence", 0.0) < float(class_conf):
                continue

            det["plugin_id"] = pid
            det["plugin_name"] = entry.get("info", {}).get("name")
            det["class"] = cls
            det["class_name"] = det.get("class_name") or global_classes.get(cls, {}).get("class_name") or str(cls)
            det["det_score"] = det.get("confidence", 0.0)
            filtered.append(det)

        logger.debug("Plugin %s filtered detections: %d", pid, len(filtered))
        return filtered, (time.time() - t0) * 1000

    def _get_camera_plugin_classes_cached(self, camera_id, plugin_id, ttl=2.0):
        key = (camera_id, plugin_id)
        now = time.time()
        with self._cam_plugin_classes_cache_lock:
            entry = self._cam_plugin_classes_cache.get(key)
            if entry and (now - entry[0] < ttl):
                return entry[1]
        try:
            data = db.get_camera_plugin_classes(camera_id, plugin_id)
        except Exception:
            data = []
        with self._cam_plugin_classes_cache_lock:
            self._cam_plugin_classes_cache[key] = (now, data)
        return data

    def _submit_inference_futures(self, camera_id, small, scale, plugin_ids, face_enabled):
        futures = {}
        if face_enabled and self._face_model and self._face_model.is_loaded:
            futures["faces"] = self._executor.submit(self._run_face_detection, camera_id, small, scale)
        for pid in plugin_ids:
            with self._plugin_models_lock:
                entry = self._plugin_models.get(pid)
            if entry and entry["model"].is_loaded:
                futures[f"obj_{pid}"] = self._executor.submit(self._run_plugin, pid, small, scale, camera_id)
        return futures

    def _collect_futures(self, futures):
        faces, objects, face_ms, obj_ms = [], [], 0.0, 0.0
        for key, fut in futures.items():
            try:
                data, ms = fut.result(timeout=30)
                if key == "faces":
                    faces = data
                    face_ms = ms
                else:
                    objects.extend(data)
                    obj_ms += ms
            except Exception as e:
                logger.warning("Inference future failed for key %s: %s", key, e, exc_info=True)
        return faces, objects, face_ms, obj_ms

    def _identify_faces(self, camera_id, faces, existing_trackers, aggressive_mode, max_identify, small):
        identifies_used = 0
        for f in faces:
            if f.get("identity"):
                continue

            best, best_iou = None, 0
            for ent in existing_trackers:
                iou = _iou(ent.get("bbox"), f.get("bbox")) if ent.get("bbox") and f.get("bbox") else 0
                if iou > best_iou:
                    best_iou, best = iou, ent

            if best and best_iou > 0.5 and best.get("identity"):
                f["identity"] = best.get("identity")
                f["confidence"] = best.get("confidence")
                f["embedding"] = f.get("embedding") or best.get("embedding")
                f["liveness"] = best.get("liveness", 1.0)
                f["gender"] = f.get("gender") or best.get("gender", "unknown")
                f["gender_confidence"] = max(float(f.get("gender_confidence", 0.0)), float(best.get("gender_confidence", 0.0)))
                continue

            if aggressive_mode and identifies_used >= max_identify:
                continue

            if self._face_model and self._face_model.is_loaded and f.get("embedding") is not None:
                try:
                    cam_thresh = None
                    with contextlib.suppress(Exception):
                        cam_thresh = self._get_camera_threshold_cached(camera_id)
                    idinfo, score = self._face_model.identify(f.get("embedding"), threshold=cam_thresh)
                    f["identity"] = idinfo
                    f["confidence"] = score
                    if not aggressive_mode:
                        liveness_required = config.liveness_global()
                        if idinfo and not liveness_required:
                            row = db.get_known_face(idinfo.get("id"))
                            if row and row.get("liveness_required"):
                                liveness_required = True
                        f["liveness"] = self._face_model.check_liveness(small, {"bbox": f.get("bbox")}) if liveness_required else 1.0
                    identifies_used += 1
                except Exception:
                    logger.debug("Identify failed for face in camera %s", camera_id, exc_info=True)

    def _get_camera_threshold_cached(self, camera_id, ttl=2.0):
        now = time.time()
        with self._camera_threshold_cache_lock:
            entry = self._camera_threshold_cache.get(camera_id)
            if entry and (now - entry[0] < ttl):
                return entry[1]
        try:
            val = db.get_camera_face_threshold(camera_id)
        except Exception:
            val = None
        with self._camera_threshold_cache_lock:
            self._camera_threshold_cache[camera_id] = (now, val)
        return val

    def _get_camera_settings_cached(self, camera_id, ttl=2.0):
        now = time.time()
        with self._camera_settings_cache_lock:
            entry = self._camera_settings_cache.get(camera_id)
            if entry and (now - entry[0] < ttl):
                return entry[1]
        try:
            cam = db.get_camera(camera_id)
        except Exception:
            cam = None
        with self._camera_settings_cache_lock:
            self._camera_settings_cache[camera_id] = (now, cam)
        return cam

    def _rebuild_trackers(self, camera_id, frame, faces, objects, max_trackers):
        state = self._get_camera_state(camera_id)
        entries = []
        for f in faces[:max_trackers]:
            bbox = f.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            tr = self._make_tracker()
            if tr is None:
                continue
            try:
                tr.init(frame, (int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
            except Exception:
                logger.debug("Tracker init failed for face in camera %s", camera_id, exc_info=True)
                continue
            entries.append(
                {
                    "tracker": tr,
                    "type": "face",
                    "bbox": [x1, y1, x2, y2],
                    "identity": f.get("identity"),
                    "confidence": f.get("confidence"),
                    "det_score": f.get("det_score"),
                    "embedding": f.get("embedding"),
                    "liveness": f.get("liveness", 1.0),
                    "gender": f.get("gender", "unknown"),
                    "gender_confidence": f.get("gender_confidence", 0.0),
                    "last_seen": time.time(),
                }
            )

        for o in objects[:max_trackers]:
            bbox = o.get("bbox")
            if not bbox:
                continue
            x1, y1, x2, y2 = bbox
            tr = self._make_tracker()
            if tr is None:
                continue
            try:
                tr.init(frame, (int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
            except Exception:
                logger.debug("Tracker init failed for object in camera %s", camera_id, exc_info=True)
                continue
            entries.append(
                {
                    "tracker": tr,
                    "type": "object",
                    "bbox": [x1, y1, x2, y2],
                    "plugin_id": o.get("plugin_id"),
                    "plugin_name": o.get("plugin_name"),
                    "class": o.get("class"),
                    "det_score": o.get("det_score"),
                    "last_seen": time.time(),
                }
            )

        with state.trackers_lock:
            state.trackers = entries

    def _get_ghost_settings(self, now):
        if now - self._ghost_settings_ts > 5.0:
            try:
                self._ghost_settings_cache = {
                    "enabled": db.get_bool("ghost_bbox_enabled", True),
                    "ttl": float(db.get_float("ghost_bbox_ttl", 0.35) or 0.35),
                    "max_v": float(db.get_float("ghost_bbox_max_velocity", 28) or 28),
                }
            except Exception:
                pass
            self._ghost_settings_ts = now
        ghost_ttl = self._ghost_settings_cache.get("ttl", _GHOST_TTL)
        max_ghost_v = self._ghost_settings_cache.get("max_v", _MAX_GHOST_V)
        ghost_feature_on = self._ghost_settings_cache.get("enabled", True)
        return ghost_ttl, max_ghost_v, ghost_feature_on

    @staticmethod
    def _build_grid(entries):
        grid = {}
        sizes = []
        for e in entries:
            pb = e.get("bbox")
            if not pb:
                continue
            w = max(1.0, pb[2] - pb[0])
            h = max(1.0, pb[3] - pb[1])
            sizes.append(max(w, h))
        avg_sz = max(16, int(sum(sizes) / len(sizes))) if sizes else 80
        bucket = max(48, int(avg_sz * 1.5))
        for idx, e in enumerate(entries):
            pb = e.get("bbox")
            if not pb:
                continue
            cx = int((pb[0] + pb[2]) / 2.0)
            cy = int((pb[1] + pb[3]) / 2.0)
            grid.setdefault((cx // bucket, cy // bucket), []).append((idx, e))
        return grid, bucket

    @staticmethod
    def _nearby_candidates(grid, bucket, box):
        cx = int((box[0] + box[2]) / 2.0)
        cy = int((box[1] + box[3]) / 2.0)
        gx, gy = cx // bucket, cy // bucket
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cell = (gx + dx, gy + dy)
                if cell in grid:
                    cand.extend(grid[cell])
        return cand

    def _apply_smoothing(self, camera_id, faces, objects):
        state = self._get_camera_state(camera_id)
        with state.smoothing_lock:
            prev = state.smoothing_state
            ghost_store = state.ghost_store
            now = time.time()

            ghost_ttl, max_ghost_v, ghost_feature_on = self._get_ghost_settings(now)

            new_face_state = []
            face_grid, face_bucket = self._build_grid(prev.get("faces", []))
            matched_face_prev: set = set()

            for f in faces:
                curr_box = f.get("bbox")
                if not curr_box:
                    new_face_state.append(
                        {
                            "id": None,
                            "bbox": None,
                            "vx": 0.0,
                            "vy": 0.0,
                            "last_seen": now,
                            "_ident_info": None,
                            "_confidence": None,
                            "_liveness": 1.0,
                            "_det_score": 0.0,
                            "_gender": "unknown",
                            "_gender_conf": 0.0,
                        }
                    )
                    continue
                ident = None
                if isinstance(f.get("identity"), dict):
                    ident = f["identity"].get("id")

                matched = None
                if ident:
                    for p in prev["faces"]:
                        if p.get("id") == ident:
                            matched = p
                            break

                if not matched:
                    candidates = self._nearby_candidates(face_grid, face_bucket, curr_box)
                    best_iou = 0
                    for _idx, p in candidates:
                        pb = p.get("bbox")
                        if not pb:
                            continue
                        i = _iou(pb, curr_box)
                        if i > best_iou:
                            best_iou, matched = i, p if i > 0.3 else None

                if not matched:
                    candidates = self._nearby_candidates(face_grid, face_bucket, curr_box)
                    best_dist = None
                    for _idx, p in candidates:
                        pb = p.get("bbox")
                        if not pb:
                            continue
                        cx1 = (pb[0] + pb[2]) / 2.0
                        cy1 = (pb[1] + pb[3]) / 2.0
                        cx2 = (curr_box[0] + curr_box[2]) / 2.0
                        cy2 = (curr_box[1] + curr_box[3]) / 2.0
                        dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
                        norm = max(1.0, curr_box[2] - curr_box[0], curr_box[3] - curr_box[1])
                        rel = dist / norm
                        if best_dist is None or rel < best_dist:
                            best_dist, matched = rel, p if rel < 3.0 else None

                vx = vy = 0.0
                if matched and matched.get("bbox"):
                    pb = matched["bbox"]
                    cx_prev = (pb[0] + pb[2]) / 2.0
                    cy_prev = (pb[1] + pb[3]) / 2.0
                    cx_curr = (curr_box[0] + curr_box[2]) / 2.0
                    cy_curr = (curr_box[1] + curr_box[3]) / 2.0
                    move_dist = ((cx_prev - cx_curr) ** 2 + (cy_prev - cy_curr) ** 2) ** 0.5
                    box_sz = max(1.0, curr_box[2] - curr_box[0], curr_box[3] - curr_box[1])
                    rel_move = move_dist / box_sz
                    alpha = 0.25 if rel_move > 0.7 else 0.35 if rel_move > 0.4 else 0.5 if rel_move > 0.2 else 0.7
                    f["bbox"] = _smooth_bbox(pb, curr_box, alpha=alpha)
                    sb = f["bbox"]
                    vx = (sb[0] + sb[2]) / 2.0 - cx_prev
                    vy = (sb[1] + sb[3]) / 2.0 - cy_prev
                    matched_face_prev.add(id(matched))

                new_face_state.append(
                    {
                        "id": ident,
                        "bbox": f.get("bbox"),
                        "vx": vx,
                        "vy": vy,
                        "last_seen": now,
                        "_ident_info": f.get("identity"),
                        "_confidence": f.get("confidence"),
                        "_liveness": f.get("liveness", 1.0),
                        "_det_score": f.get("det_score", 0.0),
                        "_gender": f.get("gender", "unknown"),
                        "_gender_conf": f.get("gender_confidence", 0.0),
                    }
                )

            new_ghost_faces = []
            if ghost_feature_on:
                for g in ghost_store["faces"]:
                    if now - g["last_seen"] > ghost_ttl:
                        continue

                    if any(f.get("bbox") and _iou(f["bbox"], g["bbox"]) > 0.25 for f in faces if f.get("bbox")):
                        continue
                    gvx = max(-max_ghost_v, min(max_ghost_v, g.get("vx", 0.0) * 0.8))
                    gvy = max(-max_ghost_v, min(max_ghost_v, g.get("vy", 0.0) * 0.8))
                    pb = g["bbox"]
                    new_ghost_faces.append(
                        {
                            **g,
                            "bbox": [int(pb[0] + gvx), int(pb[1] + gvy), int(pb[2] + gvx), int(pb[3] + gvy)],
                            "vx": gvx,
                            "vy": gvy,
                        }
                    )

                for p in prev.get("faces", []):
                    if id(p) in matched_face_prev or not p.get("bbox"):
                        continue
                    if now - p.get("last_seen", now) > 0.5:
                        continue
                    vx = max(-max_ghost_v, min(max_ghost_v, p.get("vx", 0.0)))
                    vy = max(-max_ghost_v, min(max_ghost_v, p.get("vy", 0.0)))
                    new_ghost_faces.append(
                        {
                            "bbox": list(p["bbox"]),
                            "vx": vx,
                            "vy": vy,
                            "last_seen": p.get("last_seen", now),
                            "_ident_info": p.get("_ident_info"),
                            "_confidence": p.get("_confidence"),
                            "_liveness": p.get("_liveness", 1.0),
                            "_det_score": p.get("_det_score", 0.0),
                            "_gender": p.get("_gender", "unknown"),
                            "_gender_conf": p.get("_gender_conf", 0.0),
                        }
                    )
            ghost_store["faces"] = new_ghost_faces

            new_obj_state = []
            obj_grid, obj_bucket = self._build_grid(prev.get("objects", []))
            matched_obj_prev: set = set()

            for o in objects:
                curr_box = o.get("bbox")
                if not curr_box:
                    new_obj_state.append(
                        {
                            "plugin": o.get("plugin_id"),
                            "class": None,
                            "bbox": None,
                            "vx": 0.0,
                            "vy": 0.0,
                            "last_seen": now,
                            "_class_name": None,
                            "_plugin_name": None,
                            "_det_score": 0.0,
                        }
                    )
                    continue
                plugin = o.get("plugin_id")
                cls = o.get("class") or o.get("label") or o.get("class_name")
                matched, best_iou = None, 0
                candidates = self._nearby_candidates(obj_grid, obj_bucket, curr_box)
                for _idx, p in candidates:
                    if p.get("plugin") != plugin:
                        continue
                    if p.get("class") is not None and cls is not None and p.get("class") != cls:
                        continue
                    pb = p.get("bbox")
                    if not pb:
                        continue
                    i = _iou(pb, curr_box)
                    if i > best_iou:
                        best_iou, matched = i, p

                if (not matched or best_iou <= 0.3) and candidates:
                    best_dist = None
                    for _idx, p in candidates:
                        if p.get("plugin") != plugin:
                            continue
                        if p.get("class") is not None and cls is not None and p.get("class") != cls:
                            continue
                        pb = p.get("bbox")
                        if not pb:
                            continue
                        cx1 = (pb[0] + pb[2]) / 2.0
                        cy1 = (pb[1] + pb[3]) / 2.0
                        cx2 = (curr_box[0] + curr_box[2]) / 2.0
                        cy2 = (curr_box[1] + curr_box[3]) / 2.0
                        dist = ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5
                        norm = max(1.0, curr_box[2] - curr_box[0], curr_box[3] - curr_box[1])
                        rel = dist / norm
                        if best_dist is None or rel < best_dist:
                            best_dist, matched = rel, p if rel < 3.0 else None

                vx = vy = 0.0
                if matched and matched.get("bbox"):
                    sb_prev = matched["bbox"]
                    alpha = 0.6 if best_iou > 0.0 else 0.4
                    o["bbox"] = _smooth_bbox(sb_prev, curr_box, alpha=alpha)
                    sb = o["bbox"]
                    vx = (sb[0] + sb[2]) / 2.0 - (sb_prev[0] + sb_prev[2]) / 2.0
                    vy = (sb[1] + sb[3]) / 2.0 - (sb_prev[1] + sb_prev[3]) / 2.0
                    matched_obj_prev.add(id(matched))

                new_obj_state.append(
                    {
                        "plugin": plugin,
                        "class": cls,
                        "bbox": o.get("bbox"),
                        "vx": vx,
                        "vy": vy,
                        "last_seen": now,
                        "_class_name": o.get("class_name"),
                        "_plugin_name": o.get("plugin_name"),
                        "_det_score": o.get("det_score", 0.0),
                    }
                )

            new_ghost_objects = []
            if ghost_feature_on:
                for g in ghost_store["objects"]:
                    if now - g["last_seen"] > ghost_ttl:
                        continue
                    if any(
                        o.get("bbox") and _iou(o["bbox"], g["bbox"]) > 0.25 and o.get("plugin_id") == g.get("plugin")
                        for o in objects
                        if o.get("bbox")
                    ):
                        continue
                    gvx = max(-max_ghost_v, min(max_ghost_v, g.get("vx", 0.0) * 0.8))
                    gvy = max(-max_ghost_v, min(max_ghost_v, g.get("vy", 0.0) * 0.8))
                    pb = g["bbox"]
                    new_ghost_objects.append(
                        {
                            **g,
                            "bbox": [int(pb[0] + gvx), int(pb[1] + gvy), int(pb[2] + gvx), int(pb[3] + gvy)],
                            "vx": gvx,
                            "vy": gvy,
                        }
                    )
                for p in prev.get("objects", []):
                    if id(p) in matched_obj_prev or not p.get("bbox"):
                        continue
                    if now - p.get("last_seen", now) > 0.5:
                        continue
                    vx = max(-max_ghost_v, min(max_ghost_v, p.get("vx", 0.0)))
                    vy = max(-max_ghost_v, min(max_ghost_v, p.get("vy", 0.0)))
                    new_ghost_objects.append(
                        {
                            "bbox": list(p["bbox"]),
                            "vx": vx,
                            "vy": vy,
                            "last_seen": p.get("last_seen", now),
                            "plugin": p.get("plugin"),
                            "class": p.get("class"),
                            "_class_name": p.get("_class_name"),
                            "_plugin_name": p.get("_plugin_name"),
                            "_det_score": p.get("_det_score", 0.0),
                        }
                    )
            ghost_store["objects"] = new_ghost_objects

            prev["faces"] = new_face_state
            prev["objects"] = new_obj_state
            state.smoothing_state = prev
            state.ghost_store = ghost_store

            ghost_faces = [
                {
                    "bbox": g["bbox"],
                    "identity": g.get("_ident_info"),
                    "confidence": g.get("_confidence"),
                    "liveness": g.get("_liveness", 1.0),
                    "det_score": g.get("_det_score", 0.0),
                    "embedding": None,
                    "gender": g.get("_gender", "unknown"),
                    "gender_confidence": g.get("_gender_conf", 0.0),
                    "ghost": True,
                }
                for g in ghost_store["faces"]
            ]

            ghost_objects = [
                {
                    "bbox": g["bbox"],
                    "class": g.get("class"),
                    "class_name": g.get("_class_name"),
                    "plugin_id": g.get("plugin"),
                    "plugin_name": g.get("_plugin_name"),
                    "det_score": g.get("_det_score", 0.0),
                    "ghost": True,
                }
                for g in ghost_store["objects"]
            ]

        return ghost_faces, ghost_objects

    def process_frame(self, frame, camera_id):
        self.ensure_initialized()
        state = self._get_camera_state(camera_id)

        with state.counter_lock:
            state.frame_counter += 1
            frame_idx = state.frame_counter

        _, aggressive_mode, max_identify, max_trackers = self._read_frame_settings()
        small, scale = self._scale_for_mode(frame, aggressive_mode)

        plugin_ids = self.get_plugins_for_camera(camera_id)
        face_enabled = self._is_face_enabled(camera_id)

        futures = self._submit_inference_futures(camera_id, small, scale, plugin_ids, face_enabled)
        faces, objects, face_ms, obj_ms = self._collect_futures(futures)

        logger.debug("Frame %d: faces=%d objects=%d", frame_idx, len(faces), len(objects))

        objects = self._filter_allowed_objects(objects)
        if faces:
            self._identify_faces_for_frame(camera_id, faces, aggressive_mode, max_identify, small)

        if faces or objects:
            self._rebuild_trackers(camera_id, frame, faces, objects, max_trackers)

        ghost_faces, ghost_objects = self._apply_smoothing(camera_id, faces, objects)

        return {
            "faces": faces,
            "objects": objects,
            "ghost_faces": ghost_faces,
            "ghost_objects": ghost_objects,
            "face_time_ms": face_ms,
            "object_time_ms": obj_ms,
        }

    def _filter_allowed_objects(self, objects):
        with self._plugin_models_lock:
            allowed_pids = set(self._plugin_models.keys())
        return [o for o in objects if o.get("plugin_id") in allowed_pids]

    def _identify_faces_for_frame(self, camera_id, faces, aggressive_mode, max_identify, small):
        state = self._get_camera_state(camera_id)
        with state.trackers_lock:
            existing_trackers = list(state.trackers)
        self._identify_faces(camera_id, faces, existing_trackers, aggressive_mode, max_identify, small)

    def _is_face_enabled(self, camera_id):
        try:
            cam = self._get_camera_settings_cached(camera_id)
            return True if cam is None else bool(cam.get("face_recognition", 1))
        except Exception:
            return True


_instance = None
_instance_lock = threading.Lock()


def get_manager():
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DetectorManager()
    return _instance


def notify_plugins_changed():
    try:
        m = get_manager()
        m.invalidate_camera_cache()
        m.reload()
        m.clear_camera_state()
        try:
            from backend.camera.camera_manager import get_camera_manager

            get_camera_manager().clear_all_states()
        except Exception:
            logger.debug("Failed to clear camera states", exc_info=True)
    except Exception:
        logger.warning("notify_plugins_changed failed", exc_info=True)
