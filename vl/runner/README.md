# Active factory build boundary

The control plane and generated-code runtime are deliberately separate:

1. `claim` has GitHub OIDC, validates the queue response, strips the job/lease credentials from schema-v1 `build-contract.json`, and uploads the lease separately for `callback`.
2. `build` has no `id-token` permission and receives only the sanitized contract plus this pinned harness. Fixed dependency manifests are prepared before generated source can execute. npm is restricted to `https://registry.npmjs.org`, uses exact versions, and disables lifecycle scripts. Deno generated imports must already be cached.
3. Generated analyze/check/build commands run as uid/gid 65534 with no-new-privileges in a new network, PID, mount, UTS, and IPC namespace. Host credential/runtime locations (`/home`, `/root`, `/run`, `/tmp`, `/var/tmp`, `/dev/shm`, and `/etc/shadow`) are masked. A cgroup and `prlimit` bound CPU, memory, processes, file size, and wall time. A 4 GiB loopback filesystem bounds aggregate disk use, and output symlinks are rejected.
4. `callback` obtains a fresh OIDC token and accepts only the fixed result schema and a SHA-256 artifact identity.

The isolation certification workflow executes the hostile fixture rather than inferring PASS from this structure. Its retained artifact is the evidence required before Issue #68 can close.
