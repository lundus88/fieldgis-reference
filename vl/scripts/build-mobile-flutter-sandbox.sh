#!/usr/bin/env bash
set -euo pipefail

# Execute generated Flutter analyze/build in a credential-free, network-disabled
# container using caches prepared from a pristine trusted template.
#
# Usage:
#   build-mobile-flutter-sandbox.sh <workspace> <builder_key>

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <workspace> <builder_key>" >&2
  exit 64
fi

WORKSPACE="$1"
BUILDER="$2"
IMAGE='ghcr.io/cirruslabs/flutter:3.38.1@sha256:01cf49cb0586bd9ece557683b0fd5ce44b9dad1073f05a584afd56b746ae9a5f'

[ "$BUILDER" = 'mobile-flutter-v1' ] || { echo "unsupported builder: $BUILDER" >&2; exit 65; }
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 70; }
ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/pubspec.yaml" ] || { echo "missing pubspec.yaml" >&2; exit 66; }
[ -f "$ROOT/.vl-mobile-cache-prepared" ] || { echo "trusted mobile cache was not prepared" >&2; exit 67; }
[ -s "$ROOT/.flutter-sdk-cache/engine.stamp" ] || { echo "writable Flutter SDK cache is missing" >&2; exit 69; }

mkdir -p "$ROOT/.home" "$ROOT/.pub-cache" "$ROOT/.gradle"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# No host env, credential file, Docker socket, home directory, or network is
# exposed. All writable build/cache state is contained inside the workspace.
# The generated build remains non-root; only Flutter's workspace-local bin/cache
# is mounted over the root-owned SDK cache required by the upstream image.
docker run --rm \
  --user "${HOST_UID}:${HOST_GID}" \
  --network none \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --pids-limit 256 \
  --memory 4g \
  --cpus 2 \
  --workdir /workspace \
  --mount "type=bind,src=${ROOT},dst=/workspace" \
  --mount "type=bind,src=${ROOT}/.flutter-sdk-cache,dst=/sdks/flutter/bin/cache" \
  --env HOME=/workspace/.home \
  --env PUB_CACHE=/workspace/.pub-cache \
  --env GRADLE_USER_HOME=/workspace/.gradle \
  --env CI=true \
  --env FLUTTER_SUPPRESS_ANALYTICS=true \
  --env FLUTTER_ALREADY_LOCKED=true \
  --env GIT_CONFIG_COUNT=1 \
  --env GIT_CONFIG_KEY_0=safe.directory \
  --env GIT_CONFIG_VALUE_0=/sdks/flutter \
  "$IMAGE" /bin/bash -lc 'set -euo pipefail; flutter --no-version-check pub get --offline; flutter --no-version-check analyze --no-fatal-infos --no-pub; flutter --no-version-check build apk --debug --no-pub'

APK="$ROOT/build/app/outputs/flutter-apk/app-debug.apk"
[ -s "$APK" ] || { echo "missing Android APK" >&2; exit 68; }
sha256sum "$APK"
