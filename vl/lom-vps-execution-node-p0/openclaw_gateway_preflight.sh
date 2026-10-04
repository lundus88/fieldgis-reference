#!/usr/bin/env bash
set -euo pipefail
umask 077

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$HOME/.local/state/lom-openclaw-preflight/$STAMP}"
mkdir -p "$OUT"
chmod 700 "$OUT"

CURRENT_USER="$(id -un)"
EXPECTED_USER="${OPENCLAW_EXPECTED_USER:-}"
if [[ -n "$EXPECTED_USER" && "$CURRENT_USER" != "$EXPECTED_USER" ]]; then
  {
    printf 'schema=lom.openclaw-gateway-preflight/1\n'
    printf 'status=RUNTIME_USER_MISMATCH\n'
    printf 'expected_user=%s\n' "$EXPECTED_USER"
    printf 'user=%s\n' "$CURRENT_USER"
  } > "$OUT/summary.txt"
  chmod 600 "$OUT/summary.txt"
  printf '%s\n' "$OUT"
  exit 3
fi

OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw 2>/dev/null || true)}"
if [[ -z "$OPENCLAW_BIN" ]]; then
  {
    printf 'schema=lom.openclaw-gateway-preflight/1\n'
    printf 'status=OPENCLAW_NOT_FOUND\n'
    printf 'user=%s\n' "$CURRENT_USER"
  } > "$OUT/summary.txt"
  chmod 600 "$OUT/summary.txt"
  printf '%s\n' "$OUT"
  exit 2
fi

if [[ ! -x "$OPENCLAW_BIN" ]]; then
  {
    printf 'schema=lom.openclaw-gateway-preflight/1\n'
    printf 'status=OPENCLAW_NOT_EXECUTABLE\n'
    printf 'user=%s\n' "$CURRENT_USER"
    printf 'openclaw_path=%s\n' "$OPENCLAW_BIN"
  } > "$OUT/summary.txt"
  chmod 600 "$OUT/summary.txt"
  printf '%s\n' "$OUT"
  exit 4
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

capture version "$OPENCLAW_BIN" --version
capture update_status "$OPENCLAW_BIN" update status --json
capture update_dry_run "$OPENCLAW_BIN" update --dry-run --json
capture health "$OPENCLAW_BIN" health
capture gateway_status "$OPENCLAW_BIN" gateway status --deep --json
capture doctor_lint "$OPENCLAW_BIN" doctor --lint --json

{
  printf 'schema=lom.openclaw-gateway-preflight/1\n'
  printf 'status=CAPTURED\n'
  printf 'observed_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'uid=%s\n' "$(id -u)"
  printf 'user=%s\n' "$CURRENT_USER"
  printf 'openclaw_path=%s\n' "$OPENCLAW_BIN"
  printf 'version=%s\n' "$(tr '\n' ' ' < "$OUT/version.out" | sed 's/[[:space:]]\+/ /g' | cut -c1-240)"
  cat "$OUT/exit-codes.txt"
} > "$OUT/summary.txt"

chmod 600 "$OUT"/*
sha256sum "$OUT"/*.out "$OUT"/*.err "$OUT/summary.txt" > "$OUT/SHA256SUMS" 2>/dev/null || true
chmod 600 "$OUT/SHA256SUMS" 2>/dev/null || true

printf '%s\n' "$OUT"
