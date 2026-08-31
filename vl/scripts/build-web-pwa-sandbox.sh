#!/usr/bin/env bash
set -euo pipefail

# Production wrapper for VL web-react-v1 / pwa-react-v1 generated builds.
# Dependency installation happens outside this wrapper with lifecycle scripts disabled.
# Only the generated build command executes inside the credential-free sandbox.
#
# Usage:
#   build-web-pwa-sandbox.sh <workspace> <builder_key>

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <workspace> <builder_key>" >&2
  exit 64
fi

WORKSPACE="$1"
BUILDER="$2"

case "$BUILDER" in
  web-react-v1|pwa-react-v1) ;;
  *) echo "unsupported builder: $BUILDER" >&2; exit 65 ;;
esac

ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/package.json" ] || { echo "missing package.json" >&2; exit 66; }
[ -d "$ROOT/node_modules" ] || { echo "missing node_modules; install dependencies first with --ignore-scripts" >&2; exit 67; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SANDBOX="$SCRIPT_DIR/run-untrusted-sandbox.sh"
[ -x "$SANDBOX" ] || { echo "sandbox runner not executable" >&2; exit 68; }

# Build generated code inside isolated container. No host secrets/OIDC/network are passed.
"$SANDBOX" node:22-bookworm "$ROOT" -- /bin/bash -lc 'npm run build'

[ -s "$ROOT/dist/index.html" ] || { echo "missing dist/index.html" >&2; exit 69; }
if [ "$BUILDER" = "pwa-react-v1" ]; then
  [ -s "$ROOT/dist/manifest.webmanifest" ] || { echo "missing PWA manifest" >&2; exit 70; }
  [ -s "$ROOT/dist/sw.js" ] || { echo "missing PWA service worker" >&2; exit 71; }
fi

rm -rf "$ROOT/.vercel/output"
mkdir -p "$ROOT/.vercel/output/static"
cp -R "$ROOT/dist/." "$ROOT/.vercel/output/static/"
printf '%s\n' '{"version":3}' > "$ROOT/.vercel/output/config.json"

[ -s "$ROOT/.vercel/output/config.json" ] || exit 72
[ -s "$ROOT/.vercel/output/static/index.html" ] || exit 73

OUT="$ROOT/../vl-web-build.tgz"
tar -C "$ROOT" -czf "$OUT" .vercel/output package.json package-lock.json
sha256sum "$OUT"
