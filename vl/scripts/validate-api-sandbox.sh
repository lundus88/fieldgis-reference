#!/usr/bin/env bash
set -euo pipefail

# Production wrapper for VL api-service-v1 generated validation.
# Generated Deno code is checked only inside the credential-free sandbox.
# Network remains disabled; unresolved dependencies fail closed.
# Dependency resolution is prepared host-side without executing generated code.
#
# Usage:
#   validate-api-sandbox.sh <workspace> <builder_key>

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <workspace> <builder_key>" >&2
  exit 64
fi

WORKSPACE="$1"
BUILDER="$2"

[ "$BUILDER" = "api-service-v1" ] || { echo "unsupported builder: $BUILDER" >&2; exit 65; }

ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -s "$ROOT/index.ts" ] || { echo "missing index.ts" >&2; exit 66; }
[ -d "$ROOT/.deno-cache" ] || { echo "missing Deno dependency cache; prepare it with deno cache --no-check" >&2; exit 67; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SANDBOX="$SCRIPT_DIR/run-untrusted-sandbox.sh"
[ -x "$SANDBOX" ] || { echo "sandbox runner not executable" >&2; exit 68; }

# --cached-only is the network boundary: every import must already be in the workspace cache.
"$SANDBOX" denoland/deno:2.5.6 "$ROOT" -- env DENO_DIR=/workspace/.deno-cache deno check --cached-only index.ts

OUT="$ROOT/../vl-api-build.tgz"
tar -C "$ROOT" -czf "$OUT" .
sha256sum "$OUT"
