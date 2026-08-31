#!/usr/bin/env bash
set -euo pipefail

# Prepare runner-owned Flutter/Android toolchain state plus dependency/build
# caches from a pristine trusted template BEFORE generated artifacts are overlaid.
#
# The pinned Cirrus image contains root-owned Flutter SDK files and may not ship
# every Android component required by Flutter 3.38.1. Generated code must never
# gain root or network access. Trusted bootstrap containers therefore have no host
# bind mounts/secrets; they only stream pinned toolchain bytes to stdout. Host-side
# tar extraction makes those bytes runner-owned. Generated builds later run
# non-root, offline, with prepared Android components mounted read-only.
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
BUILD_TOOLS_VERSION='35.0.0'
COMPILE_SDK='36'
CMAKE_VERSION='3.22.1'

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 70; }
command -v tar >/dev/null 2>&1 || { echo "tar is required" >&2; exit 71; }
ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/pubspec.yaml" ] || { echo "missing pubspec.yaml" >&2; exit 66; }
[ -f "$ROOT/android/app/build.gradle.kts" ] || { echo "expected pristine Flutter Android template" >&2; exit 67; }

mkdir -p \
  "$ROOT/.home" \
  "$ROOT/.pub-cache" \
  "$ROOT/.gradle" \
  "$ROOT/.flutter-sdk" \
  "$ROOT/.android-sdk-components"
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

# Flutter 3.38.1 requires compileSdk 36 and NDK 28.2.13676358; the current AGP
# toolchain also requests Build Tools 35.0.0 and CMake 3.22.1. Install those exact
# components only inside an ephemeral trusted container, then stream just their SDK
# directories to stdout. No host path or secret is visible during this network-enabled bootstrap.
ANDROID_READY="$ROOT/.android-sdk-components/.vl-android-components-ready"
if [ ! -f "$ANDROID_READY" ]; then
  find "$ROOT/.android-sdk-components" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
  docker run --rm \
    --network bridge \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 256 \
    --memory 4g \
    --cpus 2 \
    "$IMAGE" /bin/bash -lc "set -euo pipefail
      sdkmanager_path=\$(command -v sdkmanager || true)
      if [ -z \"\$sdkmanager_path\" ]; then
        sdkmanager_path=\$(find /opt/android-sdk-linux -type f -path '*/bin/sdkmanager' | sort | tail -n 1)
      fi
      [ -n \"\$sdkmanager_path\" ]
      \"\$sdkmanager_path\" --sdk_root=/opt/android-sdk-linux \
        'ndk;$NDK_VERSION' \
        'build-tools;$BUILD_TOOLS_VERSION' \
        'platforms;android-$COMPILE_SDK' \
        'cmake;$CMAKE_VERSION' >&2
      /bin/tar -C /opt/android-sdk-linux -cf - \
        'ndk/$NDK_VERSION' \
        'build-tools/$BUILD_TOOLS_VERSION' \
        'platforms/android-$COMPILE_SDK' \
        'cmake/$CMAKE_VERSION'" \
    | tar -C "$ROOT/.android-sdk-components" -xf - --no-same-owner
  printf '%s\n' "ndk=$NDK_VERSION build-tools=$BUILD_TOOLS_VERSION platform=android-$COMPILE_SDK cmake=$CMAKE_VERSION" > "$ANDROID_READY"
fi

[ -s "$ROOT/.android-sdk-components/ndk/$NDK_VERSION/source.properties" ] || { echo "required Android NDK missing" >&2; exit 73; }
[ -x "$ROOT/.android-sdk-components/build-tools/$BUILD_TOOLS_VERSION/aapt2" ] || { echo "required Android Build Tools missing" >&2; exit 74; }
[ -s "$ROOT/.android-sdk-components/platforms/android-$COMPILE_SDK/android.jar" ] || { echo "required Android platform missing" >&2; exit 75; }
[ -x "$ROOT/.android-sdk-components/cmake/$CMAKE_VERSION/bin/cmake" ] || { echo "required Android CMake missing" >&2; exit 77; }
[ "$(stat -c '%u' "$ROOT/.android-sdk-components/ndk/$NDK_VERSION/source.properties")" = "$HOST_UID" ] || { echo "Android components are not runner-owned" >&2; exit 76; }

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
  --mount "type=bind,src=${ROOT}/.android-sdk-components/ndk,dst=/opt/android-sdk-linux/ndk,readonly" \
  --mount "type=bind,src=${ROOT}/.android-sdk-components/build-tools,dst=/opt/android-sdk-linux/build-tools,readonly" \
  --mount "type=bind,src=${ROOT}/.android-sdk-components/platforms,dst=/opt/android-sdk-linux/platforms,readonly" \
  --mount "type=bind,src=${ROOT}/.android-sdk-components/cmake,dst=/opt/android-sdk-linux/cmake,readonly" \
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
printf '%s\n' 'trusted-template-toolchain-prepared-v7' > "$ROOT/.vl-mobile-cache-prepared"
