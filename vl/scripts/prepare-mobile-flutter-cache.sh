#!/usr/bin/env bash
set -euo pipefail

# Prepare dependency/tool caches from a pristine trusted Flutter template BEFORE
# generated artifacts are overlaid. The container has network access only during
# this trusted preparation phase and never inherits host secrets or OIDC values.
#
# Usage:
#   prepare-mobile-flutter-cache.sh <workspace>

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <workspace>" >&2
  exit 64
fi

WORKSPACE="$1"
IMAGE='ghcr.io/cirruslabs/flutter:3.38.1@sha256:01cf49cb0586bd9ece557683b0fd5ce44b9dad1073f05a584afd56b746ae9a5f'

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 70; }
ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/pubspec.yaml" ] || { echo "missing pubspec.yaml" >&2; exit 66; }
[ -f "$ROOT/android/app/build.gradle.kts" ] || { echo "expected pristine Flutter Android template" >&2; exit 67; }

mkdir -p "$ROOT/.home" "$ROOT/.pub-cache" "$ROOT/.gradle"
rm -f "$ROOT/.vl-mobile-cache-prepared"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# This phase MUST run before any generated/untrusted file is written into ROOT.
# It warms pub/Gradle/Android build caches using only the trusted Flutter template.
docker run --rm \
  --user "${HOST_UID}:${HOST_GID}" \
  --network bridge \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --pids-limit 256 \
  --memory 4g \
  --cpus 2 \
  --workdir /workspace \
  --mount "type=bind,src=${ROOT},dst=/workspace" \
  --env HOME=/workspace/.home \
  --env PUB_CACHE=/workspace/.pub-cache \
  --env GRADLE_USER_HOME=/workspace/.gradle \
  --env CI=true \
  --env FLUTTER_SUPPRESS_ANALYTICS=true \
  --env GIT_CONFIG_COUNT=1 \
  --env GIT_CONFIG_KEY_0=safe.directory \
  --env GIT_CONFIG_VALUE_0=/sdks/flutter \
  "$IMAGE" /bin/bash -lc 'set -euo pipefail; flutter --no-version-check pub get; flutter --no-version-check build apk --debug --no-pub'

# Do not allow the trusted warm-up artifact to be mistaken for a generated build.
rm -rf "$ROOT/build"
printf '%s\n' 'trusted-template-cache-prepared-v1' > "$ROOT/.vl-mobile-cache-prepared"
