#!/usr/bin/env bash
set -euo pipefail
umask 077

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="\${1:-$HOME/.local/state/lom-openclaw-preflight/$STAMP}"
mkdir -p "$OUT"
chmod 700 "$OUT"

if ! command -v openclaw >/dev/null 2>&1; then
  printf 'OPENCLAW_NOT_FOUND\n' > "$OUT/summary.txt"
  printf '%s\n' "$OUT"
  exit 2
fi

capture() {
  local name="$1"
  shift
  set +e
  "$@" >"$OUT/$name.out" 2>"$OUT/$name.err"
  local rc=$?
  set -e
  printf '%s=%s\n' "$name" "$rc" >> "$OUT/exit-codes.txt"
  return 0
}

capture version openclaw --version
capture update_status openclaw update status --json
capture update_dry_run openclaw update --dry-run --json
capture health openclaw health
capture gateway_status openclaw gateway status --deep --json
capture doctor_lint openclaw doctor --lint --json

{
  printf 'schema=lom.openclaw-gateway-preflight/1\n'
  printf 'observed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'uid=%s\n' "$(id -u)"
  printf 'user=%s\n' "$(id -un)"
  printf 'openclaw_path=%s\n' "$(command -v openclaw)"
  printf 'version=%s\n' "$(tr '\n' ' ' < "$OUT/version.out" | sed 's/[[:space:]]\+/ /g' | cut -c1-240)"
  cat "$OUT/exit-codes.txt"
} > "$OUT/summary.txt"

chmod 600 "$OUT"/*
sha256sum "$OUT"/*.out "$OUT"/*.err "$OUT/summary.txt" > "$OUT/SHA256SUMS" 2>/dev/null || true
chmod 600 "$OUT/SHA256SUMS" 2>/dev/null || true

printf '%s\n' "$OUT"
