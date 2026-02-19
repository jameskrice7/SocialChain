#!/usr/bin/env bash
# build-desktop.sh – Build the SocialChain desktop app for the current platform.
#
# Usage:
#   ./build-desktop.sh           # build for the current OS
#   ./build-desktop.sh --win     # build Windows installer (cross-compile)
#   ./build-desktop.sh --mac     # build macOS DMG (requires macOS)
#   ./build-desktop.sh --linux   # build Linux AppImage/deb
#
# Prerequisites:
#   • Node.js ≥ 18  (https://nodejs.org)
#   • npm ≥ 9
#   • Python 3.8+   (https://python.org)  – required at runtime on end-user machines
#     OR PyInstaller if you want a fully self-contained bundle (see BUNDLE_PYTHON below).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Optional: bundle the Python backend with PyInstaller ─────────────────────
# Set BUNDLE_PYTHON=1 to embed the Python interpreter + Flask app in the package.
# This makes the installer fully self-contained but significantly larger (~80 MB+).
BUNDLE_PYTHON="${BUNDLE_PYTHON:-0}"

echo "╔══════════════════════════════════════════════╗"
echo "║     SocialChain Desktop Build Script         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Install Node.js dependencies ─────────────────────────────────────────
echo "[1/4] Installing Node.js dependencies..."
npm install --save-dev electron electron-builder
echo "      ✓ npm packages installed"

# ── 2. (Optional) Bundle Python backend with PyInstaller ─────────────────────
if [ "$BUNDLE_PYTHON" = "1" ]; then
    echo "[2/4] Bundling Python backend with PyInstaller..."
    pip install pyinstaller -q
    pip install -r requirements.txt -q
    pyinstaller \
        --name socialchain-server \
        --onefile \
        --distpath electron/assets \
        --workpath /tmp/pyinstaller-build \
        --specpath /tmp/pyinstaller-spec \
        --hidden-import flask \
        --hidden-import cryptography \
        --hidden-import requests \
        run.py
    echo "      ✓ Python bundle created at electron/assets/socialchain-server"
else
    echo "[2/4] Skipping Python bundling (BUNDLE_PYTHON=0)."
    echo "      End users must have Python 3.8+ and run:"
    echo "        pip install -r requirements.txt"
fi

# ── 3. Determine build target from argument ───────────────────────────────────
echo "[3/4] Determining build target..."
TARGET_FLAG=""
case "${1:-}" in
    --win)   TARGET_FLAG="--win";   TARGET_NAME="Windows" ;;
    --mac)   TARGET_FLAG="--mac";   TARGET_NAME="macOS"   ;;
    --linux) TARGET_FLAG="--linux"; TARGET_NAME="Linux"   ;;
    "")
        if [[ "$OSTYPE" == "darwin"* ]]; then
            TARGET_FLAG="--mac";   TARGET_NAME="macOS"
        elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
            TARGET_FLAG="--win";   TARGET_NAME="Windows"
        else
            TARGET_FLAG="--linux"; TARGET_NAME="Linux"
        fi
        ;;
    *)
        echo "Unknown flag: ${1}"
        echo "Usage: $0 [--win|--mac|--linux]"
        exit 1
        ;;
esac
echo "      ✓ Building for $TARGET_NAME"

# ── 4. Run electron-builder ───────────────────────────────────────────────────
echo "[4/4] Packaging with electron-builder..."
npx electron-builder $TARGET_FLAG
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Build complete! Installer is in dist/       ║"
echo "╚══════════════════════════════════════════════╝"
