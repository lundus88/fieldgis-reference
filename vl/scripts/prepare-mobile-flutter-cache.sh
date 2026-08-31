#!/usr/bin/env bash
set -euo pipefail

# Prepare a runner-owned Flutter toolchain plus dependency/build caches from a
# pristine trusted template BEFORE generated artifacts are overlaid.
#
# The pinned Cirrus Flutter image owns parts of /sdks/flutter as root with modes
# that an arbitrary UID cannot safely read or update. Generated code must still
# run non-root. We therefore stream the trusted Flutter SDK out of a root,
# read-only, network-disabled container and extract it on the host as the GitHub
# runner user. Every later Flutter invocation uses that ephemeral runner-owned
# SDK copy; generated code is never granted root privileges.
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
command -v tar >/dev/null 2>&1 || { echo "tar is required" >&2; exit 71; }
ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/pubspec.yaml" ] || { echo "missing pubspec.yaml" >&2; exit 66; }
[ -f "$ROOT/android/app/build.gradle.kts" ] || { echo "expected pristine Flutter Android template" >&2; exit 67; }

mkdir -p "$ROOT/.home" "$ROOT/.pub-cache" "$ROOT/.gradle" "$ROOT/.flutter-sdk"
rm -f "$ROOT/.vl-mobile-cache-prepared"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# Trusted bootstrap only. The root container has no network, no host bind mount,
# a read-only root filesystem and zero Linux capabilities. It can only stream the
# already-pinned SDK to stdout. Host-side tar extraction makes the ephemeral SDK
# runner-owned, including upstream files that were root-only in the image.
if [ ! -x "$ROOT/.flutter-sdk/bin/flutter" ]; then
  find "$ROOT/.flutter-sdk" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  docker run --rm \
    --network none \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 128 \
    --memory 2g \
    --cpus 1 \
    "$IMAGE" /bin/tar -C /sdks/flutter -cf - . \
    | tar -C "$ROOT/.flutter-sdk" -xf - --no-same-owner
fi

[ -x "$ROOT/.flutter-sdk/bin/flutter" ] || { echo "failed to prepare runner-owned Flutter SDK" >&2; exit 68; }
[ -s "$ROOT/.flutter-sdk/bin/cache/engine.stamp" ] || { echo "runner-owned Flutter SDK cache is incomplete" >&2; exit 69; }
[ "$(stat -c '%u' "$ROOT/.flutter-sdk/bin/flutter")" = "$HOST_UID" ] || { echo "Flutter SDK is not runner-owned" >&2; exit 72; }

# This phase MUST run before any generated/untrusted file is written into ROOT.
# It warms pub/Gradle/Android caches using only the trusted Flutter template.
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
  --env FLUTTER_ROOT=/workspace/.flutter-sdk \
  --env FLUTTER_SUPPRESS_ANALYTICS=true \
  --env GIT_CONFIG_COUNT=1 \
  --env GIT_CONFIG_KEY_0=safe.directory \
  --env GIT_CONFIG_VALUE_0=/workspace/.flutter-sdk \
  "$IMAGE" /bin/bash -lc 'set -euo pipefail; /workspace/.flutter-sdk/bin/flutter --no-version-check pub get; /workspace/.flutter-sdk/bin/flutter --no-version-check build apk --debug --no-pub'

# Do not allow the trusted warm-up artifact to be mistaken for a generated build.
rm -rf "$ROOT/build"
printf '%s\n' 'trusted-template-toolchain-prepared-v4' > "$ROOT/.vl-mobile-cache-prepared"
