#!/usr/bin/env bash
set -euo pipefail

# VL generated-code sandbox.
# Default mode preserves the historical isolated writable workspace.
# P1 secure mode (VL_SANDBOX_EPHEMERAL=1) stages the workspace into a temporary
# host directory and copies back only explicitly whitelisted export paths.
#
# Usage:
#   run-untrusted-sandbox.sh <image> <workspace> -- <command> [args...]
#
# Optional host-only environment:
#   VL_SANDBOX_EPHEMERAL=1
#   VL_SANDBOX_EXPORTS="dist,.vl-sandbox-result.json"

if [ "$#" -lt 4 ] || [ "$3" != "--" ]; then
  echo "usage: $0 <image> <workspace> -- <command> [args...]" >&2
  exit 64
fi

IMAGE="$1"
WORKSPACE="$2"
shift 3

if ! command -v docker >/dev/null 2>&1; then
  echo "VL sandbox: docker is required" >&2
  exit 70
fi

ROOT="$(cd "$WORKSPACE" && pwd -P)"
if [ ! -d "$ROOT" ]; then
  echo "VL sandbox: workspace not found" >&2
  exit 66
fi

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"
EPHEMERAL="${VL_SANDBOX_EPHEMERAL:-0}"
EXPORTS="${VL_SANDBOX_EXPORTS:-}"
RUN_ROOT="$ROOT"
TEMP_ROOT=""

cleanup() {
  if [ -n "$TEMP_ROOT" ] && [ -d "$TEMP_ROOT" ]; then
    chmod -R u+rwX "$TEMP_ROOT" 2>/dev/null || true
    rm -rf "$TEMP_ROOT"
  fi
}
trap cleanup EXIT INT TERM

validate_relative_path() {
  case "$1" in
    ""|/*|*'..'*|*$'\n'*|*$'\r'*) return 1 ;;
    *) return 0 ;;
  esac
}

if [ "$EPHEMERAL" = "1" ]; then
  if find "$ROOT" \( -type b -o -type c -o -type p -o -type s \) -print -quit | grep -q .; then
    echo "VL sandbox: special host file in workspace forbidden" >&2
    exit 75
  fi
  while IFS= read -r -d '' link; do
    resolved="$(readlink -f "$link" || true)"
    case "$resolved" in
      "$ROOT"|"$ROOT"/*) ;;
      *) echo "VL sandbox: symlink escape forbidden: $link" >&2; exit 76 ;;
    esac
  done < <(find "$ROOT" -type l -print0)

  TEMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/vl-sandbox.XXXXXX")"
  RUN_ROOT="$TEMP_ROOT/workspace"
  mkdir -p "$RUN_ROOT"
  tar -C "$ROOT" --exclude='./.git' --exclude='./.git/*' -cf - . | tar -C "$RUN_ROOT" -xf -
fi

set +e
docker run --rm \
  --user "${HOST_UID}:${HOST_GID}" \
  --network none \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --pids-limit 256 \
  --memory 2g \
  --cpus 2 \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=256m \
  --tmpfs /run:rw,noexec,nosuid,size=64m \
  --workdir /workspace \
  --mount "type=bind,src=${RUN_ROOT},dst=/workspace" \
  --env HOME=/tmp \
  --env CI=true \
  "$IMAGE" "$@"
rc=$?
set -e

if [ "$rc" -ne 0 ]; then
  exit "$rc"
fi

if [ "$EPHEMERAL" = "1" ] && [ -n "$EXPORTS" ]; then
  IFS=',' read -r -a export_paths <<< "$EXPORTS"
  for rel in "${export_paths[@]}"; do
    rel="${rel#"${rel%%[![:space:]]*}"}"
    rel="${rel%"${rel##*[![:space:]]}"}"
    if ! validate_relative_path "$rel"; then
      echo "VL sandbox: invalid export path: $rel" >&2
      exit 77
    fi
    src="$RUN_ROOT/$rel"
    dst="$ROOT/$rel"
    if [ ! -e "$src" ]; then
      echo "VL sandbox: requested export missing: $rel" >&2
      exit 78
    fi
    real_src="$(readlink -f "$src" || true)"
    case "$real_src" in
      "$RUN_ROOT"|"$RUN_ROOT"/*) ;;
      *) echo "VL sandbox: export escaped ephemeral workspace: $rel" >&2; exit 79 ;;
    esac
    if find "$src" -type l -print -quit 2>/dev/null | grep -q .; then
      echo "VL sandbox: symlink export forbidden: $rel" >&2
      exit 80
    fi
    rm -rf "$dst"
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
  done
fi
