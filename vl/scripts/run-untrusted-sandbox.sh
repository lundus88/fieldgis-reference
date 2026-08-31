#!/usr/bin/env bash
set -euo pipefail

# VL generated-code sandbox.
# Runs untrusted/generated commands inside a Docker container with:
# - no network
# - no inherited host environment / GitHub OIDC variables
# - no Linux capabilities
# - no privilege escalation
# - bounded CPU, memory, processes and writable workspace
#
# Usage:
#   run-untrusted-sandbox.sh <image> <workspace> -- <command> [args...]

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

# Do not pass --env-file, host env, sockets, credentials or home directories.
# /workspace is the only writable host mount.
exec docker run --rm \
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
  --mount "type=bind,src=${ROOT},dst=/workspace" \
  --env HOME=/tmp \
  --env CI=true \
  "$IMAGE" "$@"
