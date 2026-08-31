#!/usr/bin/env bash
set -euo pipefail

# Prepare runner-owned Flutter/Android toolchain state plus dependency/build
# caches from a pristine trusted template BEFORE generated artifacts are overlaid.
#
# The pinned Cirrus image contains root-owned Flutter SDK files and does not ship
# Flutter 3.38.1's required NDK 28.2.13676358. Generated code must never gain root
# or network access. Trusted bootstrap containers therefore have no host bind
# mounts/secrets; they only stream pinned toolchain bytes to stdout. Host-side tar
# extraction makes those bytes runner-owned. Generated builds later run non-root,
# offline, with the prepared NDK mounted read-only into the Android SDK.
#
# Usage:
#   prepare-mobile-flutter-cache.sh <workspace>

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <workspace>" >&2
  exit 64
fi

WORKSPACE="$1"
IMAGE='ghcr.io/cirruslabs/flutter:3.38.1@sha256:01cf49cb0586bd9ece557683b0fd5ce44b9dad1073f05a584afd56b746ae9a5f'
NDK_VERSION='28.2.13676358'

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 70; }
command -v tar >/dev/null 2>&1 || { echo "tar is required" >&2; exit 71; }
ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/pubspec.yaml" ] || { echo "missing pubspec.yaml" >&2; exit 66; }
[ -f "$ROOT/android/app/build.gradle.kts" ] || { echo "expected pristine Flutter Android template" >&2; exit 67; }

mkdir -p "$ROOT/.home" "$ROOT/.pub-cache" "$ROOT/.gradle" "$ROOT/.flutter-sdk" "$ROOT/.android-ndk/$NDK_VERSION"
rm -f "$ROOT/.vl-mobile-cache-prepared"

HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# Trusted Flutter SDK bootstrap. Root exists only inside a read-only, no-network,
# capability-free container with no host mount. The host runner owns extraction.
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

# Flutter 3.38.1 requires NDK 28.2.13676358. The trusted bootstrap container may
# use network only to install that exact component into its ephemeral SDK, then
# streams only the NDK directory to stdout. It receives no host mounts or secrets.
if [ ! -s "$ROOT/.android-ndk/$NDK_VERSION/source.properties" ]; then
  find "$ROOT/.android-ndk/$NDK_VERSION" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  docker run --rm \
    --network bridge \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 256 \
    --memory 4g \
    --cpus 2 \
    "$IMAGE" /bin/bash -lc "set -eu; sdkmanager_path=\$(command -v sdkmanager || true); if [ -z \"\$sdkmanager_path\" ]; then sdkmanager_path=\$(find /opt/android-sdk-linux -type f -path '*/bin/sdkmanager' | sort | tail -n 1); fi; [ -n \"\$sdkmanager_path\" ]; \"\$sdkmanager_path\" --sdk_root=/opt/android-sdk-linux 'ndk;$NDK_VERSION' >&2; /bin/tar -C '/opt/android-sdk-linux/ndk/$NDK_VERSION' -cf - ." \
    | tar -C "$ROOT/.android-ndk/$NDK_VERSION" -xf - --no-same-owner
fi

[ -s "$ROOT/.android-ndk/$NDK_VERSION/source.properties" ] || { echo "failed to prepare required Android NDK" >&2; exit 73; }
[ "$(stat -c '%u' "$ROOT/.android-ndk/$NDK_VERSION/source.properties")" = "$HOST_UID" ] || { echo "Android NDK cache is not runner-owned" >&2; exit 74; }

# Trusted pristine-template warm-up. Generated files do not exist yet. Flutter
# runs non-root; network is allowed only here to warm pub/Gradle dependencies.
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
  --mount "type=bind,src=${ROOT}/.android-ndk,dst=/opt/android-sdk-linux/ndk,readonly" \
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
printf '%s\n' 'trusted-template-toolchain-prepared-v5' > "$ROOT/.vl-mobile-cache-prepared"
