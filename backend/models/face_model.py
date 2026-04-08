import contextlib
import glob
import logging
import os
import threading
import traceback
import zipfile

import numpy as np

from backend.repository import db
from utils import config
from utils.embedding_utils import bytes_to_embedding

_logger = logging.getLogger(__name__)

AVAILABLE_MODELS = {
    "buffalo_l": "buffalo_l  - Large (most accurate, recommended)",
    "buffalo_m": "buffalo_m  - Medium (balanced)",
    "buffalo_s": "buffalo_s  - Small (faster, less accurate)",
    "buffalo_sc": "buffalo_sc - Small + shape (fast)",
    "antelopev2": "antelopev2 - Highest accuracy (large)",
}

ALLOWED_MODULES = ["detection", "recognition", "genderage"]


def normalize_gender(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, (list, tuple)):
        if not value:
            return "unknown"
        value = value[0]
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return "unknown"
        if value.size >= 2:
            # Typical genderage vector: [female_score, male_score].
            try:
                female_score = float(value.flat[0])
                male_score = float(value.flat[1])
                return "male" if male_score >= female_score else "female"
            except Exception:
                value = float(value.flat[0])
        else:
            value = float(value.flat[0])
    if isinstance(value, (int, float, np.integer, np.floating)):
        return "male" if float(value) >= 0.5 else "female"
    text = str(value).strip().lower()
    if text in ("male", "m", "man", "boy", "1"):
        return "male"
    if text in ("female", "f", "woman", "girl", "0"):
        return "female"
    return "unknown"


def _extract_gender_info(face_obj) -> tuple[str, float]:
    try:
        raw_gender = getattr(face_obj, "gender", None)
    except Exception:
        raw_gender = None
    gender = normalize_gender(raw_gender)
    if gender == "unknown":
        return gender, 0.0
    if isinstance(raw_gender, (int, float, np.integer, np.floating)):
        conf = min(1.0, max(0.0, abs(float(raw_gender) - 0.5) * 2.0))
        return gender, conf
    if isinstance(raw_gender, np.ndarray) and raw_gender.size >= 2:
        try:
            female_score = float(raw_gender.flat[0])
            male_score = float(raw_gender.flat[1])
            conf = min(1.0, max(0.0, abs(male_score - female_score)))
            return gender, conf
        except Exception:
            pass
    return gender, 1.0


def get_allowed_modules() -> list[str]:
    import json as _json

    try:
        raw = db.get_setting("insightface_allowed_modules", None)
        if raw:
            mods = _json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(mods, list) and mods:
                # One-time migration: pre-gender configs may lack genderage.
                migrated = db.get_bool("insightface_allowed_modules_genderage_migrated", False)
                if not migrated and "genderage" not in mods:
                    mods = list(mods) + ["genderage"]
                    with contextlib.suppress(Exception):
                        db.set_setting("insightface_allowed_modules", _json.dumps(mods))
                    with contextlib.suppress(Exception):
                        db.set_setting("insightface_allowed_modules_genderage_migrated", "1")
                return mods
    except Exception:
        pass
    return list(ALLOWED_MODULES)


def set_allowed_modules(modules: list[str]) -> None:
    import json as _json

    try:
        db.set_setting("insightface_allowed_modules", _json.dumps(modules))
    except Exception:
        pass


_cached_model_name: str | None = None
_cached_providers: list[str] | None = None


def _get_model_name() -> str:
    global _cached_model_name
    if _cached_model_name is not None:
        _logger.info(" Cache HIT: model_name=%s", _cached_model_name)
        return _cached_model_name

    _logger.info(" Cache MISS: Loading model_name from database")
    try:
        name = db.get_setting("insightface_model_name", "buffalo_l") or "buffalo_l"
        _cached_model_name = name if name in AVAILABLE_MODELS else "buffalo_l"
        _logger.info("Cached model_name=%s", _cached_model_name)
    except Exception:
        _cached_model_name = "buffalo_l"
    return _cached_model_name


def _detect_providers() -> list[str]:
    global _cached_providers
    if _cached_providers is not None:
        _logger.info(" Cache HIT: providers=%s", _cached_providers)
        return _cached_providers

    _logger.info(" Cache MISS: Detecting providers")
    try:
        import onnxruntime as ort

        ort.get_available_providers()
    except Exception:
        _cached_providers = ["CPUExecutionProvider"]
        _logger.info("Cached providers=%s", _cached_providers)
        return _cached_providers

    _cached_providers = ["CPUExecutionProvider"]
    _logger.info("Cached providers=%s (forced CPU)", _cached_providers)
    return _cached_providers


def _find_insightface_root(hint: str = "", model_name: str = "") -> str | None:
    if not model_name:
        model_name = _get_model_name()
    candidates = [os.path.expanduser("~/.insightface")]
    try:
        configured = db.get_setting("insightface_model_dir", "") or ""
        if configured:
            candidates.append(configured)
            candidates.append(os.path.dirname(configured))
    except Exception:
        pass
    if hint:
        candidates.append(hint)
        candidates.append(os.path.dirname(hint))
    candidates += [
        "models_weights/insightface",
        "models_weights",
        os.path.join(os.path.dirname(__file__), "..", "..", "models_weights", "insightface"),
        ".",
    ]

    checked = set()

    def _has_model(root: str) -> bool:
        model_dir = os.path.join(root, "models", model_name)
        return os.path.isdir(model_dir) and bool(glob.glob(os.path.join(model_dir, "*.onnx")))

    for raw in candidates:
        root = os.path.abspath(raw)
        if root in checked:
            continue
        checked.add(root)
        if not os.path.isdir(root):
            continue
        if _has_model(root):
            return root
        for zp in glob.glob(os.path.join(root, "**", f"{model_name}.zip"), recursive=True):
            try:
                dest = os.path.join(root, "models")
                os.makedirs(dest, exist_ok=True)
                with zipfile.ZipFile(zp, "r") as zf:
                    zf.extractall(dest)
                if _has_model(root):
                    return root
            except Exception:
                continue

    return None


class FaceModel:
    def __init__(self):
        self._app = None
        self._loaded = False
        self._loading = False
        self._load_lock = threading.Lock()
        self._root_used: str | None = None
        self._model_name: str = _get_model_name()
        self._providers_used: list[str] = []
        self._last_load_error: str | None = None
        self._known_matrix: np.ndarray | None = None
        self._known_rows: list[dict] = []
        self._known_cache_dirty: bool = True
        self._gender_diag_logged: bool = False

    def load(self, model_dir: str = "") -> None:
        with self._load_lock:
            if self._loaded:
                return
            if self._loading:
                return
            self._loading = True

        try:
            self._load_internal(model_dir)
        finally:
            with self._load_lock:
                self._loading = False

    def reload(self, model_dir: str = "") -> None:
        global _cached_model_name, _cached_providers
        _cached_model_name = None
        with self._load_lock:
            self._loaded = False
            self._loading = False
            self._app = None
        self.load(model_dir)

    def load_async(self, model_dir: str = "", callback=None) -> threading.Thread:
        def _async_load():
            try:
                self.load(model_dir)
                if callback:
                    callback(success=True, error=None)
            except Exception as e:
                _logger.error("Async load failed: %s", e, exc_info=True)
                if callback:
                    callback(success=False, error=str(e))

        thread = threading.Thread(target=_async_load, daemon=True, name="FaceModelAsyncLoad")
        thread.start()
        return thread

    def _load_internal(self, model_dir: str = "") -> None:
        try:
            import onnxruntime as ort
            from insightface.app import FaceAnalysis

            with contextlib.suppress(Exception):
                ort.set_default_logger_severity(3)

            self._model_name = _get_model_name()
            providers = _detect_providers()

            root = None
            try:
                cached = db.get_setting("insightface_root_cache", "") or ""
                if cached and os.path.isdir(cached):
                    model_dir_check = os.path.join(cached, "models", self._model_name)
                    if os.path.isdir(model_dir_check) and glob.glob(os.path.join(model_dir_check, "*.onnx")):
                        root = cached
            except Exception:
                pass

            if root is None:
                root = _find_insightface_root(hint=model_dir, model_name=self._model_name)
            if not root:
                root = os.path.expanduser("~/.insightface")

            self._providers_used = providers

            def _try_load(prov_list, det_size):
                app = FaceAnalysis(
                    name=self._model_name,
                    root=root,
                    providers=prov_list,
                    allowed_modules=get_allowed_modules(),
                )
                ctx = -1
                app.prepare(ctx_id=ctx, det_size=det_size)
                return app

            try:
                det_size = (224, 224)
                self._app = _try_load(providers, det_size)
                self._root_used = root
                self._last_load_error = None
                self._loaded = True
                with contextlib.suppress(Exception):
                    db.set_setting("insightface_root_cache", root)
                return
            except Exception:
                _logger.warning("InsightFace GPU load failed, falling back to CPU", exc_info=True)
                self._last_load_error = f"Preferred providers init failed:\n{traceback.format_exc()}"

                try:
                    global _cached_providers
                    _cached_providers = ["CPUExecutionProvider"]
                except Exception:
                    pass

            try:
                cpu_prov = ["CPUExecutionProvider"]
                self._app = _try_load(cpu_prov, (640, 640))
                self._providers_used = cpu_prov
                self._root_used = root
                self._loaded = True
                self._last_load_error = None
                with contextlib.suppress(Exception):
                    db.set_setting("insightface_root_cache", root)
                return
            except Exception:
                prev = self._last_load_error or ""
                self._last_load_error = f"CPU fallback failed:\n{traceback.format_exc()}\nPrevious:\n{prev}"
                self._loaded = False
                raise Exception(self._last_load_error) from None

        except Exception:
            self._last_load_error = f"Load failed:\n{traceback.format_exc()}"
            self._loaded = False
            raise

    def invalidate_known_cache(self) -> None:
        self._known_cache_dirty = True

    def get_submodel_status(self) -> list[dict]:
        if self._root_used is None:
            return []
        model_dir = os.path.join(self._root_used, "models", self._model_name)
        if not os.path.isdir(model_dir):
            return []
        loaded_tasks: set[str] = set()
        if self._app is not None and hasattr(self._app, "models"):
            loaded_tasks = set(self._app.models.keys())
        allowed = get_allowed_modules()
        result = []
        for onnx_path in sorted(glob.glob(os.path.join(model_dir, "*.onnx"))):
            fname = os.path.basename(onnx_path)
            name_lower = fname.lower()
            if "2d106" in name_lower:
                task = "landmark_2d_106"
            elif "1k3d68" in name_lower or "3d68" in name_lower:
                task = "landmark_3d_68"
            elif "genderage" in name_lower or "gender" in name_lower:
                task = "genderage"
            elif "det_" in name_lower or ("det" in name_lower and "2d" not in name_lower and "3d" not in name_lower):
                task = "detection"
            elif any(k in name_lower for k in ("w600k", "recog", "mbf", "r50", "r100")):
                task = "recognition"
            else:
                task = "unknown"
            result.append(
                {
                    "filename": fname,
                    "task": task,
                    "loaded": task in loaded_tasks,
                    "required": task in ("detection", "recognition"),
                    "enabled": task in allowed,
                }
            )
        return result

    def _rebuild_known_matrix(self) -> None:
        known = db.get_known_faces(enabled_only=True)
        if not known:
            self._known_matrix = None
            self._known_rows = []
            self._known_cache_dirty = False
            return

        rows, embeddings = [], []
        for row in known:
            emb_bytes = row.get("embedding")
            if not emb_bytes:
                continue
            try:
                emb = bytes_to_embedding(emb_bytes)
                embeddings.append(emb)
                rows.append(row)
            except Exception:
                continue

        if not embeddings:
            self._known_matrix = None
            self._known_rows = []
            self._known_cache_dirty = False
            return

        matrix = np.stack(embeddings).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        np.divide(matrix, np.maximum(norms, 1e-8), out=matrix)
        self._known_matrix = matrix
        self._known_rows = rows
        self._known_cache_dirty = False

    @property
    def providers_used(self) -> list[str]:
        return self._providers_used

    @property
    def last_load_error(self) -> str | None:
        return self._last_load_error

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def is_loading(self) -> bool:
        return self._loading

    def _normalize_embedding(self, emb) -> np.ndarray | None:
        if emb is None:
            return None
        arr = np.asarray(emb, dtype=np.float32)
        if arr.size == 0:
            return None
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr /= norm
        return arr

    def detect_faces(self, frame) -> list[dict]:
        if not self._loaded or self._app is None:
            return []
        try:
            faces = self._app.get(frame)
        except Exception:
            _logger.warning("detect_faces: inference error", exc_info=True)
            return []
        results = []
        gender_enabled = db.get_bool("gender_inference_enabled", True)
        for f in faces:
            try:
                bbox = [int(b) for b in f.bbox]
                emb = self._normalize_embedding(f.embedding if hasattr(f, "embedding") else None)
                gender, gender_conf = _extract_gender_info(f) if gender_enabled else ("unknown", 0.0)
                results.append(
                    {
                        "bbox": bbox,
                        "embedding": emb,
                        "det_score": float(f.det_score),
                        "gender": gender,
                        "gender_confidence": float(gender_conf),
                    }
                )
            except Exception:
                continue
        if gender_enabled and faces and not self._gender_diag_logged:
            with contextlib.suppress(Exception):
                sample_gender = getattr(faces[0], "gender", None)
                _logger.info("Gender sample output: type=%s value=%r", type(sample_gender).__name__, sample_gender)
            self._gender_diag_logged = True
        return results

    def get_embedding(self, frame):
        faces = self.detect_faces(frame)
        if not faces:
            return None
        return faces[0].get("embedding")

    def identify(self, embedding, threshold: float | None = None) -> tuple[dict | None, float]:
        if embedding is None:
            return None, 0.0

        if threshold is None:
            try:
                threshold = float(config.face_threshold())
            except Exception:
                threshold = 0.45

        if self._known_cache_dirty:
            self._rebuild_known_matrix()

        if self._known_matrix is None:
            return None, 0.0

        query = self._normalize_embedding(embedding)
        if query is None:
            return None, 0.0

        scores = self._known_matrix @ query
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score >= threshold:
            row = self._known_rows[best_idx]
            return {"id": row.get("id"), "name": row.get("name"), "confidence": best_score}, best_score
        return None, best_score

    def check_liveness(self, frame, _face_info: dict) -> float:
        return 1.0



