#!/usr/bin/env bash
set -euo pipefail

# Production wrapper for VL gis-web-v1 generated builds.
# Dependencies must be installed on the host with lifecycle scripts disabled.
# Generated build logic executes only inside the credential-free sandbox.
#
# Usage:
#   build-gis-web-sandbox.sh <workspace> <builder_key>

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <workspace> <builder_key>" >&2
  exit 64
fi

WORKSPACE="$1"
BUILDER="$2"

[ "$BUILDER" = "gis-web-v1" ] || { echo "unsupported builder: $BUILDER" >&2; exit 65; }

ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/package.json" ] || { echo "missing package.json" >&2; exit 66; }
[ -d "$ROOT/node_modules" ] || { echo "missing node_modules; install dependencies first with --ignore-scripts" >&2; exit 67; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SANDBOX="$SCRIPT_DIR/run-untrusted-sandbox.sh"
[ -x "$SANDBOX" ] || { echo "sandbox runner not executable" >&2; exit 68; }

"$SANDBOX" node:22-bookworm "$ROOT" -- /bin/bash -lc 'npm run build'

[ -s "$ROOT/dist/index.html" ] || { echo "missing dist/index.html" >&2; exit 69; }
JS_BUNDLE="$(find "$ROOT/dist/assets" -type f -name '*.js' -print -quit)"
[ -n "$JS_BUNDLE" ] || { echo "missing JavaScript bundle" >&2; exit 70; }
grep -R -q '__VL_MAPLIBRE_RUNTIME__' "$ROOT/dist/assets" || { echo "missing MapLibre runtime contract" >&2; exit 71; }

rm -rf "$ROOT/.vercel/output"
mkdir -p "$ROOT/.vercel/output/static"
cp -R "$ROOT/dist/." "$ROOT/.vercel/output/static/"
printf '%s\n' '{"version":3}' > "$ROOT/.vercel/output/config.json"

[ -s "$ROOT/.vercel/output/config.json" ] || exit 72
[ -s "$ROOT/.vercel/output/static/index.html" ] || exit 73
grep -R -q '__VL_MAPLIBRE_RUNTIME__' "$ROOT/.vercel/output/static/assets" || exit 74

OUT="$ROOT/../vl-gis-build.tgz"
tar -C "$ROOT" -czf "$OUT" .vercel/output package.json package-lock.json
sha256sum "$OUT"
