#!/usr/bin/env bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT/.venv/Scripts/python.exe"
ENTRY="$ROOT/main.py"
OUT_DIR="$ROOT/build"

JOBS="${SMARTEYE_JOBS:-2}"
LTO="${SMARTEYE_LTO:-yes}"

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLD='\033[1m'; RST='\033[0m'
info()  { echo -e "${GRN}[INFO]${RST}  $*"; }
warn()  { echo -e "${YLW}[WARN]${RST}  $*"; }
error() { echo -e "${RED}[ERR ]${RST}  $*" >&2; }

if [[ ! -f "$PYTHON" ]]; then
    error "venv Python not found: $PYTHON"
    error "Make sure you opened/created the PyCharm venv first."
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

echo -e "${BLD}=== Smart Eye – Nuitka Build ===${RST}"
info "Python   : $PYTHON"
info "Entry    : $ENTRY"
info "Output   : $OUT_DIR"
info "Jobs     : $JOBS"
info "LTO      : $LTO"
info "Free RAM : ~${FREE_MB} MB"
echo ""

if (( FREE_MB > 0 && FREE_MB < 3500 )); then
    warn "Less than 3.5 GB free RAM detected."
    warn "Close all other applications before continuing."
    warn "Consider increasing your Windows page file to at least 16 GB."
    read -rp "Press Enter to continue anyway, or Ctrl-C to abort..."
    echo ""
fi

if ! "$PYTHON" -c "import nuitka" 2>/dev/null; then
    warn "nuitka not found in venv – installing now..."
    "$PYTHON" -m pip install nuitka
fi

NUITKA_VER=$("$PYTHON" -m nuitka --version 2>&1 | head -1)
info "Nuitka   : $NUITKA_VER"
echo ""

HAS_MODELS=false
if [[ -d "$ROOT/data/models" ]] && [[ -n "$(ls -A "$ROOT/data/models" 2>/dev/null)" ]]; then
    HAS_MODELS=true
    info "Model bundle detected – will be included in build"
else
    warn "No models found in data/models/ – build will exclude model bundle"
fi
echo ""

warn "Compilation will take a long time on a resource-limited machine."
warn "Do NOT open heavy applications while building."
echo ""

cd "$ROOT"

NUITKA_ARGS=(
    --standalone
    --output-dir="$OUT_DIR"
    --output-filename="SmartEye"
    
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
    
    --nofollow-import-to=numpy.distutils
    --nofollow-import-to=numpy.random.tests
    --nofollow-import-to=numpy.random.tests.test_extending
    --nofollow-import-to=onnxruntime.training
    --nofollow-import-to=onnxruntime.tools
    --nofollow-import-to=onnx.backend.test
    --nofollow-import-to=cv2.samples
    --nofollow-import-to=pyqtgraph.tests
    --nofollow-import-to=pyqtgraph.opengl
    --nofollow-import-to=pyqtgraph.exporters
    --nofollow-import-to=PySide6.QtWebEngine
    --nofollow-import-to=PySide6.QtWebEngineWidgets
    --nofollow-import-to=PySide6.QtWebEngineCore
    --nofollow-import-to=PySide6.Qt3DCore
    --nofollow-import-to=PySide6.Qt3DRender
    --nofollow-import-to=PySide6.Qt3DInput
    --nofollow-import-to=PySide6.Qt3DLogic
    --nofollow-import-to=PySide6.Qt3DAnimation
    --nofollow-import-to=PySide6.Qt3DExtras
    --nofollow-import-to=PySide6.QtCharts
    --nofollow-import-to=PySide6.QtDataVisualization
    --nofollow-import-to=PySide6.QtLocation
    --nofollow-import-to=PySide6.QtPositioning
    --nofollow-import-to=PySide6.QtRemoteObjects
    --nofollow-import-to=PySide6.QtSensors
    --nofollow-import-to=PySide6.QtSerialPort
    --nofollow-import-to=PySide6.QtTextToSpeech
    --nofollow-import-to=PySide6.QtBluetooth
    --nofollow-import-to=PySide6.QtNfc
    --nofollow-import-to=unittest
    --nofollow-import-to=test
    --nofollow-import-to=distutils
    --nofollow-import-to=setuptools
    --nofollow-import-to=pkg_resources
    --nofollow-import-to=pip
    --nofollow-import-to=doctest
    
    --noinclude-data-files=qt6webenginecore.dll
    --noinclude-data-files=qt6webenginequick.dll
    --noinclude-data-files=qt6quick.dll
    --noinclude-data-files=qt6quick3d.dll
    --noinclude-data-files=qt6quick3druntimerender.dll
    --noinclude-data-files=qt6quick3dutils.dll
    --noinclude-data-files=qt6quickcontrols2.dll
    --noinclude-data-files=qt6quickshapes.dll
    --noinclude-data-files=qt6quicktemplates2.dll
    --noinclude-data-files=qt6quicktest.dll
    --noinclude-data-files=qt6quickwidgets.dll
    --noinclude-data-files=qt6qml.dll
    --noinclude-data-files=qt6qmlmeta.dll
    --noinclude-data-files=qt6qmlmodels.dll
    --noinclude-data-files=qt6qmlworkerscript.dll
    --noinclude-data-files=qt6scxml.dll
    --noinclude-data-files=qt6spatialaudio.dll
    --noinclude-data-files=Cython/*
    --noinclude-data-files=skimage/data/*
    --noinclude-data-files=insightface/thirdparty/*
    --noinclude-data-files=pyqtgraph/examples/*
    
    --assume-yes-for-downloads
    --show-progress
    --show-memory
    --show-scons
)

if [[ "$HAS_MODELS" == true ]]; then
    NUITKA_ARGS+=(--include-data-dir="data/models=data/models")
fi

"$PYTHON" -m nuitka "${NUITKA_ARGS[@]}" "$ENTRY"

DIST_DIR="$OUT_DIR/main.dist"
EXE="$DIST_DIR/SmartEye.exe"

echo ""
echo -e "${BLD}=== Build finished ===${RST}"

if [[ -f "$EXE" ]]; then
    SIZE=$(du -sh "$EXE" 2>/dev/null | cut -f1)
    info "Executable : $EXE  ($SIZE)"
    info "Dist folder: $DIST_DIR"
    echo ""
    
    if command -v upx &> /dev/null; then
        read -rp "Compress executable with UPX? (reduces size by ~70%) [y/N] " ans
        if [[ "${ans,,}" == "y" ]]; then
            info "Compressing with UPX..."
            upx -9 "$EXE"
            SIZE_AFTER=$(du -sh "$EXE" 2>/dev/null | cut -f1)
            info "Compressed size: $SIZE_AFTER"
        fi
    else
        warn "UPX not found. Install with: choco install upx"
        warn "UPX can reduce executable size by ~70%"
    fi
    
    echo ""
    info "To run: start \"\" \"$EXE\""
    echo ""
    
    BUILD_CACHE="$OUT_DIR/main.build"
    if [[ -d "$BUILD_CACHE" ]]; then
        read -rp "Delete intermediate build cache ($BUILD_CACHE)? [y/N] " ans
        if [[ "${ans,,}" == "y" ]]; then
            rm -rf "$BUILD_CACHE"
            info "Build cache deleted."
        fi
    fi
else
    error "SmartEye.exe not found – check the Nuitka output above for errors."
    exit 1
fi