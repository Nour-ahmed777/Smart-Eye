#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT/.venv/Scripts/python.exe"
ENTRY="$ROOT/main.py"
OUT_DIR="$ROOT/build"
DIST_NAME="SmartEye"

JOBS="${SMARTEYE_JOBS:-2}"
LTO="${SMARTEYE_LTO:-no}"
INCLUDE_MODELS="${SMARTEYE_INCLUDE_MODELS:-no}"
MAX_DIST_MB="${SMARTEYE_MAX_DIST_MB:-3072}"

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLD='\033[1m'; RST='\033[0m'
info()  { echo -e "${GRN}[INFO]${RST}  $*"; }
warn()  { echo -e "${YLW}[WARN]${RST}  $*"; }
error() { echo -e "${RED}[ERR ]${RST}  $*" >&2; }

if [[ ! -f "$PYTHON" ]]; then
    error "venv Python not found: $PYTHON"
    error "Make sure the Smart-Eye venv exists first."
    exit 1
fi

if [[ ! -f "$ENTRY" ]]; then
    error "Entry point not found: $ENTRY"
    exit 1
fi

FREE_MB=$(powershell.exe -NoProfile -Command \
    "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024" 2>/dev/null \
    | tr -d '[:space:]' || echo "0")
FREE_MB=${FREE_MB%.*}

echo -e "${BLD}=== Smart Eye - Safe Nuitka Build ===${RST}"
info "Python   : $PYTHON"
info "Entry    : $ENTRY"
info "Output   : $OUT_DIR"
info "Jobs     : $JOBS"
info "LTO      : $LTO"
info "Models   : $INCLUDE_MODELS"
info "Free RAM : ~${FREE_MB} MB"
echo ""

if (( FREE_MB > 0 && FREE_MB < 3500 )); then
    warn "Less than 3.5 GB free RAM detected."
    warn "Close other applications before continuing."
    warn "Consider increasing the Windows page file to at least 16 GB."
    read -rp "Press Enter to continue anyway, or Ctrl-C to abort..."
    echo ""
fi

"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install --upgrade ordered-set zstandard nuitka

NUITKA_VER=$("$PYTHON" -m nuitka --version 2>&1 | head -1)
info "Nuitka   : $NUITKA_VER"
echo ""

HAS_MODELS=false
if [[ -d "$ROOT/data/models" ]] && [[ -n "$(ls -A "$ROOT/data/models" 2>/dev/null)" ]]; then
    HAS_MODELS=true
    info "Model bundle detected in data/models"
else
    warn "No models found in data/models/"
fi
echo ""

if [[ "$INCLUDE_MODELS" != "yes" ]]; then
    warn "Model bundle is excluded by default to prevent huge output."
    warn "Set SMARTEYE_INCLUDE_MODELS=yes if you explicitly need bundled model files."
fi

# Remove previous output so repeated builds do not accumulate stale files.
rm -rf "$OUT_DIR"

warn "Compilation can take a long time on resource-limited machines."
warn "Do NOT open heavy applications while building."
echo ""

cd "$ROOT"

NUITKA_ARGS=(
    --standalone
    --output-dir="$OUT_DIR"
    --output-filename="$DIST_NAME"
    --remove-output

    --jobs="$JOBS"
    --lto="$LTO"

    --windows-console-mode=disable

    --enable-plugin=pyside6

    --include-package=psutil
    --include-package=PySide6
    --include-package=shiboken6
    --include-package=reportlab
    --include-package=requests
    --include-package=pyqtgraph
    --include-package=onnx
    --include-package=onnxruntime
    --include-package=insightface
    --include-package=GPUtil
    --include-package=wmi
    --include-package=backend
    --include-package=frontend
    --include-package=utils
    --include-package=streamlink

    --include-package-data=reportlab
    --include-package-data=pyqtgraph
    --include-package-data=insightface
    --include-package-data=onnxruntime
    --include-package-data=streamlink

    --include-data-dir="frontend/assets=frontend/assets"
    --include-data-file="app_info.json=app_info.json"
    --include-data-file="backend/database/schema.sql=backend/database/schema.sql"

    --nofollow-import-to=PySide6.QtWebEngine
    --nofollow-import-to=PySide6.QtWebEngineWidgets
    --nofollow-import-to=PySide6.QtWebEngineCore
    --nofollow-import-to=onnxruntime.training
    --nofollow-import-to=unittest
    --nofollow-import-to=test
    --nofollow-import-to=doctest

    --noinclude-data-files=**/tests/**
    --noinclude-data-files=**/test/**

    --assume-yes-for-downloads
    --show-progress
    --show-memory
    --show-scons
)

if [[ "$HAS_MODELS" == true && "$INCLUDE_MODELS" == "yes" ]]; then
    NUITKA_ARGS+=(--include-data-dir="data/models=data/models")
fi

"$PYTHON" -m nuitka "${NUITKA_ARGS[@]}" "$ENTRY"

DIST_DIR="$OUT_DIR/main.dist"
EXE="$DIST_DIR/${DIST_NAME}.exe"

echo ""
echo -e "${BLD}=== Build finished ===${RST}"

if [[ -f "$EXE" ]]; then
    SIZE=$(du -sh "$EXE" 2>/dev/null | cut -f1)
    info "Executable : $EXE  ($SIZE)"
    info "Dist folder: $DIST_DIR"
    echo ""

    info "To run: start \"\" \"$EXE\""
    echo ""

    DIST_MB=$(du -sm "$DIST_DIR" | cut -f1)
    if (( DIST_MB > MAX_DIST_MB )); then
        error "Dist folder is ${DIST_MB} MB, over limit ${MAX_DIST_MB} MB."
        error "Rebuild without models (default) or lower dependency footprint."
        exit 2
    fi
    info "Dist size  : ${DIST_MB} MB (limit: ${MAX_DIST_MB} MB)"

    BUILD_CACHE="$OUT_DIR/main.build"
    if [[ -d "$BUILD_CACHE" ]]; then
        read -rp "Delete intermediate build cache ($BUILD_CACHE)? [y/N] " ans
        if [[ "${ans,,}" == "y" ]]; then
            rm -rf "$BUILD_CACHE"
            info "Build cache deleted."
        fi
    fi
else
    error "${DIST_NAME}.exe not found - check the Nuitka output above for errors."
    exit 1
fi
