#!/usr/bin/env bash
set -euo pipefail

# Production wrapper for VL api-service-v1 generated validation.
# Generated Deno code is checked only inside the credential-free sandbox.
# Network remains disabled; unresolved dependencies fail closed.
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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SANDBOX="$SCRIPT_DIR/run-untrusted-sandbox.sh"
[ -x "$SANDBOX" ] || { echo "sandbox runner not executable" >&2; exit 68; }

"$SANDBOX" denoland/deno:2.5.6 "$ROOT" -- check index.ts

OUT="$ROOT/../vl-api-build.tgz"
tar -C "$ROOT" -czf "$OUT" .
sha256sum "$OUT"
