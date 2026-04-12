import contextlib
import logging
import os

try:
    import cv2
except Exception:
    cv2 = None
try:
    import psutil
except Exception:
    psutil = None

logger = logging.getLogger(__name__)


def apply_limits(limit_resources: bool, max_cpu_cores: int = 1, max_ram_mb: int = 4096):
    cores = max(1, int(max_cpu_cores or 1))
    ram_mb = max(256, int(max_ram_mb or 256))
    try:
        if limit_resources:
            os.environ["OMP_NUM_THREADS"] = str(cores)
            os.environ["OPENBLAS_NUM_THREADS"] = str(cores)
            os.environ["MKL_NUM_THREADS"] = str(cores)
            os.environ["NUMEXPR_MAX_THREADS"] = str(cores)
            os.environ["OMP_THREAD_LIMIT"] = str(cores)
            th = cores
        else:
            th = max(1, os.cpu_count() or 1)
            os.environ["OMP_NUM_THREADS"] = str(th)
            os.environ["OPENBLAS_NUM_THREADS"] = str(th)
            os.environ["MKL_NUM_THREADS"] = str(th)
            os.environ["NUMEXPR_MAX_THREADS"] = str(th)
            os.environ["OMP_THREAD_LIMIT"] = str(th)
    except Exception:
        logger.exception("Failed to set thread environment variables")

    try:
        if cv2 is not None:
            cv2.setNumThreads(th)
    except Exception:
        logger.debug("Failed to set OpenCV threads", exc_info=True)

    try:
        if limit_resources:
            if psutil is not None:
                p = psutil.Process()
                with contextlib.suppress(Exception):
                    all_cpus = p.cpu_affinity()
                    if all_cpus:
                        p.cpu_affinity(all_cpus[: min(cores, len(all_cpus))])
                with contextlib.suppress(Exception):
                    p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                with contextlib.suppress(Exception):
                    p.nice(10)
            else:
                try:
                    import ctypes

                    handle = ctypes.windll.kernel32.GetCurrentProcess()
                    ctypes.windll.kernel32.SetPriorityClass(handle, 0x4000)
                except Exception:
                    pass
    except Exception:
        logger.debug("Failed to lower process priority", exc_info=True)

    try:
        if limit_resources and os.name == "nt":
            import ctypes

            max_bytes = ctypes.c_size_t(ram_mb * 1024 * 1024)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetProcessWorkingSetSize(handle, max_bytes, max_bytes)
    except Exception:
        logger.debug("Failed to set memory working set cap", exc_info=True)
