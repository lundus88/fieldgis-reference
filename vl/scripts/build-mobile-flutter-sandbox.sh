#!/usr/bin/env bash
set -euo pipefail

# Execute generated Flutter analyze/build in a credential-free, network-disabled
# container using the runner-owned Flutter toolchain and exact Android components
# prepared from a pristine trusted template.
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
NDK_VERSION='28.2.13676358'
BUILD_TOOLS_VERSION='35.0.0'
COMPILE_SDK='36'
CMAKE_VERSION='3.22.1'

[ "$BUILDER" = 'mobile-flutter-v1' ] || { echo "unsupported builder: $BUILDER" >&2; exit 65; }
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 70; }
ROOT="$(cd "$WORKSPACE" && pwd -P)"
[ -f "$ROOT/pubspec.yaml" ] || { echo "missing pubspec.yaml" >&2; exit 66; }
[ -f "$ROOT/.vl-mobile-cache-prepared" ] || { echo "trusted mobile toolchain/cache was not prepared" >&2; exit 67; }
[ -x "$ROOT/.flutter-sdk/bin/flutter" ] || { echo "runner-owned Flutter SDK is missing" >&2; exit 69; }
[ -s "$ROOT/.flutter-sdk/bin/cache/engine.stamp" ] || { echo "runner-owned Flutter SDK cache is incomplete" >&2; exit 71; }
[ -s "$ROOT/.android-sdk-components/ndk/$NDK_VERSION/source.properties" ] || { echo "required Android NDK is missing" >&2; exit 72; }
[ -x "$ROOT/.android-sdk-components/build-tools/$BUILD_TOOLS_VERSION/aapt2" ] || { echo "required Android Build Tools are missing" >&2; exit 73; }
[ -s "$ROOT/.android-sdk-components/platforms/android-$COMPILE_SDK/android.jar" ] || { echo "required Android platform is missing" >&2; exit 74; }
[ -x "$ROOT/.android-sdk-components/cmake/$CMAKE_VERSION/bin/cmake" ] || { echo "required Android CMake is missing" >&2; exit 75; }

mkdir -p "$ROOT/.home" "$ROOT/.pub-cache" "$ROOT/.gradle"
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

# No host env, credential file, Docker socket, home directory, or network is
# exposed. Prepared Android components are read-only. All other writable
# toolchain/build/cache state is contained inside ROOT. Generated code always
# executes as the unprivileged runner UID.
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
  --env FLUTTER_ALREADY_LOCKED=true \
  --env GIT_CONFIG_COUNT=1 \
  --env GIT_CONFIG_KEY_0=safe.directory \
  --env GIT_CONFIG_VALUE_0=/workspace/.flutter-sdk \
  "$IMAGE" /bin/bash -lc 'set -euo pipefail; /workspace/.flutter-sdk/bin/flutter --no-version-check pub get --offline; /workspace/.flutter-sdk/bin/flutter --no-version-check analyze --no-fatal-infos --no-pub; /workspace/.flutter-sdk/bin/flutter --no-version-check build apk --debug --no-pub'

APK="$ROOT/build/app/outputs/flutter-apk/app-debug.apk"
[ -s "$APK" ] || { echo "missing Android APK" >&2; exit 68; }
sha256sum "$APK"
