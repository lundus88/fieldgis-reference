#!/usr/bin/env bash
set -euo pipefail

# Prepare dependency/tool caches from a pristine trusted Flutter template BEFORE
# generated artifacts are overlaid. The container has network access only during
# this trusted preparation phase and never inherits host secrets or OIDC values.
#
# The pinned Cirrus Flutter image owns /sdks/flutter as root and some cache files
# are not readable by an arbitrary UID. Generated code must nevertheless remain
# non-root. We therefore stream the trusted SDK cache out of a root, read-only,
# network-disabled container and extract it on the host as the GitHub runner user.
# Later Flutter invocations bind-mount only that runner-owned cache over the image
# cache while the SDK source remains immutable/root-owned inside the image.
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

mkdir -p "$ROOT/.home" "$ROOT/.pub-cache" "$ROOT/.gradle" "$ROOT/.flutter-sdk-cache"
rm -f "$ROOT/.vl-mobile-cache-prepared"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# Trusted bootstrap only: the container runs as its image default (root) solely to
# read the root-owned Flutter cache. It has no network, no host bind mount, a
# read-only root filesystem, and all Linux capabilities dropped. Tar extraction
# happens outside the container as the runner user, so the copied cache is owned
# by HOST_UID/HOST_GID without granting generated code root privileges.
if [ ! -s "$ROOT/.flutter-sdk-cache/engine.stamp" ]; then
  find "$ROOT/.flutter-sdk-cache" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  docker run --rm \
    --network none \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 128 \
    --memory 2g \
    --cpus 1 \
    "$IMAGE" /bin/tar -C /sdks/flutter/bin/cache -cf - . \
    | tar -C "$ROOT/.flutter-sdk-cache" -xf - --no-same-owner
fi

[ -s "$ROOT/.flutter-sdk-cache/engine.stamp" ] || { echo "failed to prepare writable Flutter SDK cache" >&2; exit 68; }
[ "$(stat -c '%u' "$ROOT/.flutter-sdk-cache/engine.stamp")" = "$HOST_UID" ] || { echo "Flutter SDK cache is not runner-owned" >&2; exit 69; }

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
  --mount "type=bind,src=${ROOT}/.flutter-sdk-cache,dst=/sdks/flutter/bin/cache" \
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
printf '%s\n' 'trusted-template-cache-prepared-v3' > "$ROOT/.vl-mobile-cache-prepared"
