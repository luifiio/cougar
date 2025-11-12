#!/usr/bin/env bash
set -euo pipefail

# Fetch the CesiumMilkTruck GLB and poster into assets/models/
# Usage: ./tools/fetch_placeholder.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS_DIR="$ROOT_DIR/assets/models"
mkdir -p "$ASSETS_DIR"

GLB_URL="https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/CesiumMilkTruck/glTF-Binary/CesiumMilkTruck.glb"

POSTER_BASENAME="https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Models/master/2.0/CesiumMilkTruck/screenshot/screenshot"

GLB_OUT="$ASSETS_DIR/CesiumMilkTruck.glb"
POSTER_OUT="$ASSETS_DIR/CesiumMilkTruck-screenshot"

echo "Downloading placeholder model to: $GLB_OUT"
if command -v curl >/dev/null 2>&1; then
  curl -fL "$GLB_URL" -o "$GLB_OUT"
  # try common poster extensions but don't fail if none exist
  for ext in webp png jpg jpeg; do
    url="$POSTER_BASENAME.$ext"
    out="$POSTER_OUT.$ext"
    echo "Trying poster: $url"
    if curl -sI -f "$url" >/dev/null 2>&1; then
      curl -fL "$url" -o "$out"
      echo "Saved poster to $out"
      POSTER_OUT="$out"
      break
    fi
  done
elif command -v wget >/dev/null 2>&1; then
  wget -O "$GLB_OUT" "$GLB_URL"
  for ext in webp png jpg jpeg; do
    url="$POSTER_BASENAME.$ext"
    out="$POSTER_OUT.$ext"
    echo "Trying poster: $url"
    if wget --spider "$url" 2>/dev/null; then
      wget -O "$out" "$url"
      echo "Saved poster to $out"
      POSTER_OUT="$out"
      break
    fi
  done
else
  echo "Error: neither curl nor wget found. Please install curl or wget and re-run this script." >&2
  exit 2
fi

echo "Downloaded files:"
ls -lh "$GLB_OUT" || true
if [ -n "${POSTER_OUT-}" ] && [ -f "$POSTER_OUT" ]; then
  ls -lh "$POSTER_OUT" || true
else
  echo "No poster downloaded (not critical)."
fi

cat > "$ASSETS_DIR/README-PLACEHOLDER.md" <<'EOF'
Placeholder model: CesiumMilkTruck from Khronos glTF Sample Models

Source: https://github.com/KhronosGroup/glTF-Sample-Models/tree/master/2.0/CesiumMilkTruck
License: See the glTF-Sample-Models repo README for usage guidelines. These sample models are provided for demonstration and testing.
EOF

echo "Done. The viewer and results pages will use this local model as the default placeholder."
