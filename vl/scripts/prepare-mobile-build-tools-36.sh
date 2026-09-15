#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <workspace>" >&2
  exit 64
fi

ROOT="$(cd "$1" && pwd -P)"
IMAGE='ghcr.io/cirruslabs/flutter:3.38.1@sha256:01cf49cb0586bd9ece557683b0fd5ce44b9dad1073f05a584afd56b746ae9a5f'
VERSION='36.0.0'
DEST="$ROOT/.android-sdk-components/build-tools"

mkdir -p "$DEST"

if [ ! -x "$DEST/$VERSION/aapt2" ]; then
  docker run --rm \
    --network bridge \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --pids-limit 128 \
    --memory 2g \
    --cpus 1 \
    "$IMAGE" /bin/bash -lc "set -euo pipefail
      sdkmanager_path=\$(command -v sdkmanager || true)
      if [ -z \"\$sdkmanager_path\" ]; then
        sdkmanager_path=\$(find /opt/android-sdk-linux -type f -path '*/bin/sdkmanager' | sort | tail -n 1)
      fi
      [ -n \"\$sdkmanager_path\" ]
      \"\$sdkmanager_path\" --sdk_root=/opt/android-sdk-linux 'build-tools;$VERSION' >&2
      /bin/tar -C /opt/android-sdk-linux/build-tools -cf - '$VERSION'" \
    | tar -C "$DEST" -xf - --no-same-owner
fi

[ -x "$DEST/$VERSION/aapt2" ] || { echo "required Android Build-Tools $VERSION missing" >&2; exit 65; }
[ "$(stat -c '%u' "$DEST/$VERSION/aapt2")" = "$(id -u)" ] || { echo "Android Build-Tools $VERSION are not runner-owned" >&2; exit 66; }

printf '%s\n' "trusted-build-tools-$VERSION-prepared"
