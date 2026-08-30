#!/usr/bin/env bash
set -euo pipefail

# Runs generated-code build commands in a separate mount/PID/network namespace.
# Dependencies must be prepared by the trusted harness before this is invoked.
workspace="${1:?workspace required}"
shift
workspace="$(realpath -e -- "$workspace")"
case "$workspace" in "$GITHUB_WORKSPACE"/*) ;; *) echo 'workspace outside job root' >&2; exit 64;; esac

cpu_seconds="${VL_SANDBOX_CPU_SECONDS:-900}"
memory_bytes="${VL_SANDBOX_MEMORY_BYTES:-6442450944}"
file_bytes="${VL_SANDBOX_FILE_BYTES:-2147483648}"
processes="${VL_SANDBOX_PROCESSES:-128}"
wall_seconds="${VL_SANDBOX_WALL_SECONDS:-1200}"

disk_bytes="${VL_SANDBOX_DISK_BYTES:-4294967296}"
image="$(mktemp "${RUNNER_TEMP:-/tmp}/vl-sandbox-disk.XXXXXX")"
trap 'rm -f -- "$image"' EXIT
truncate -s "$disk_bytes" "$image"
sudo mkfs.ext4 -q -F "$image"

sudo systemd-run --scope --quiet \
  --property="MemoryMax=${memory_bytes}" --property="TasksMax=${processes}" --property="CPUQuota=200%" \
  unshare --mount --uts --ipc --net --pid --fork --mount-proc \
  env -i PATH="$PATH" HOME=/tmp/vl-home LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  bash -euo pipefail -c '
    root="$1"; image="$2"; wall="$3"; cpu="$4"; mem="$5"; file="$6"; proc="$7"; shift 7
    mount --make-rprivate /
    mkdir -p /mnt/vl-sandbox
    mount -o loop,nosuid,nodev "$image" /mnt/vl-sandbox
    mkdir /mnt/vl-sandbox/work
    cp -a -- "$root/." /mnt/vl-sandbox/work/
    mkdir -p /mnt/vl-host-output
    mount --bind "$root" /mnt/vl-host-output
    mount -o remount,bind,ro,nosuid,nodev,noexec /mnt/vl-host-output
    mount -t tmpfs -o size=256m,nosuid,nodev,noexec tmpfs /tmp
    mount --bind /dev/null /etc/shadow
    mount -t tmpfs -o size=16m,nosuid,nodev,noexec tmpfs /root
    mount -t tmpfs -o size=16m,nosuid,nodev,noexec tmpfs /home
    mount -t tmpfs -o size=16m,nosuid,nodev,noexec tmpfs /run
    mount -t tmpfs -o size=64m,nosuid,nodev,noexec tmpfs /var/tmp
    mount -t tmpfs -o size=64m,nosuid,nodev,noexec tmpfs /dev/shm
    mkdir -p /tmp/vl-home
    chown -R 65534:65534 /mnt/vl-sandbox/work /tmp/vl-home
    cd /mnt/vl-sandbox/work
    set +e
    timeout --signal=TERM --kill-after=10s "$wall" \
      prlimit --cpu="$cpu" --as="$mem" --fsize="$file" --nproc="$proc" -- \
      setpriv --reuid=65534 --regid=65534 --clear-groups --no-new-privs "$@"
    rc=$?
    set -e
    if find /mnt/vl-sandbox/work -type l -print -quit | grep -q .; then echo "sandbox output symlink forbidden" >&2; exit 65; fi
    mount -o remount,bind,rw,nosuid,nodev,noexec /mnt/vl-host-output
    cp -a -- /mnt/vl-sandbox/work/. /mnt/vl-host-output/
    exit "$rc"
  ' sandbox "$workspace" "$image" "$wall_seconds" "$cpu_seconds" "$memory_bytes" "$file_bytes" "$processes" "$@"
