#!/usr/bin/env bash
# generate-icons.sh – Generate production-quality icons for all platforms.
#
# Prerequisites:
#   • ImageMagick  (brew install imagemagick  /  apt install imagemagick)
#   • png2icns     (brew install libicns  /  apt install icnsutils)      [macOS ICNS only]
#
# Usage:
#   ./electron/assets/generate-icons.sh <source-image.png>
#
# The source image should be at least 1024x1024 px with a transparent background.
# Outputs:
#   icon.png   – 512x512 PNG  (Linux)
#   icon.ico   – multi-size ICO (Windows: 16,32,48,64,128,256)
#   icon.icns  – macOS ICNS bundle (128,256,512,1024 + @2x variants)
#   tray-icon.png – 22x22 PNG  (system tray, all platforms)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:-}"

if [[ -z "$SRC" ]]; then
    echo "Usage: $0 <source-image.png>"
    exit 1
fi

if ! command -v convert &>/dev/null; then
    echo "Error: ImageMagick 'convert' not found. Install ImageMagick first."
    exit 1
fi

echo "Generating icons from: $SRC"

# ── icon.png (512×512, Linux) ──────────────────────────────────────────────
convert "$SRC" -resize 512x512 "$SCRIPT_DIR/icon.png"
echo "  ✓ icon.png (512×512)"

# ── tray-icon.png (22×22, system tray) ────────────────────────────────────
convert "$SRC" -resize 22x22 "$SCRIPT_DIR/tray-icon.png"
echo "  ✓ tray-icon.png (22×22)"

# ── icon.ico (Windows, multi-size) ────────────────────────────────────────
convert "$SRC" \
    \( -clone 0 -resize 256x256 \) \
    \( -clone 0 -resize 128x128 \) \
    \( -clone 0 -resize  64x64  \) \
    \( -clone 0 -resize  48x48  \) \
    \( -clone 0 -resize  32x32  \) \
    \( -clone 0 -resize  16x16  \) \
    -delete 0 \
    "$SCRIPT_DIR/icon.ico"
echo "  ✓ icon.ico (16, 32, 48, 64, 128, 256)"

# ── icon.icns (macOS) ──────────────────────────────────────────────────────
if command -v png2icns &>/dev/null || command -v iconutil &>/dev/null; then
    TMP_ICONSET="$(mktemp -d)/AppIcon.iconset"
    mkdir -p "$TMP_ICONSET"

    for SIZE in 16 32 64 128 256 512; do
        convert "$SRC" -resize "${SIZE}x${SIZE}"       "$TMP_ICONSET/icon_${SIZE}x${SIZE}.png"
        convert "$SRC" -resize "$((SIZE*2))x$((SIZE*2))" "$TMP_ICONSET/icon_${SIZE}x${SIZE}@2x.png"
    done

    if command -v iconutil &>/dev/null; then
        iconutil -c icns "$TMP_ICONSET" -o "$SCRIPT_DIR/icon.icns"
    else
        png2icns "$SCRIPT_DIR/icon.icns" \
            "$TMP_ICONSET/icon_16x16.png" \
            "$TMP_ICONSET/icon_32x32.png" \
            "$TMP_ICONSET/icon_128x128.png" \
            "$TMP_ICONSET/icon_256x256.png" \
            "$TMP_ICONSET/icon_512x512.png"
    fi
    rm -rf "$TMP_ICONSET"
    echo "  ✓ icon.icns (macOS)"
else
    echo "  ⚠ Skipping icon.icns: neither iconutil (macOS) nor png2icns (Linux) found."
    echo "    On macOS: iconutil is built-in."
    echo "    On Linux: apt install icnsutils  OR  brew install libicns"
fi

echo ""
echo "All icons generated in: $SCRIPT_DIR"
