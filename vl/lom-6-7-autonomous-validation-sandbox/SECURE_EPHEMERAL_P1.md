# LOM 6.7 P1 — Secure Ephemeral Sandbox Hardening

This is an upgrade to the existing LOM 6.7 Autonomous Validation Sandbox and generated-code sandbox runner. It is not a second sandbox runtime.

## Security change

Historical sandbox isolation already enforced:

- no network;
- no inherited production credentials / OIDC secrets;
- all Linux capabilities dropped;
- no-new-privileges;
- bounded CPU, memory and process count;
- read-only container root;
- no Docker socket.

P1 closes the remaining host-workspace boundary.

In secure mode the runner:

1. validates the source workspace;
2. rejects host block/character devices, FIFOs and sockets;
3. rejects symlinks that resolve outside the source workspace;
4. copies source into a temporary host workspace;
5. excludes `.git` metadata;
6. runs the untrusted container against the temporary copy;
7. copies back only explicitly allowlisted result paths;
8. rejects symlink-based exports;
9. destroys the temporary workspace on exit.

## Activation

`VL_SANDBOX_EPHEMERAL=1`

Optional bounded exports:

`VL_SANDBOX_EXPORTS="dist,.vl-sandbox-result.json"`

Web/PWA, GIS and API validation paths use secure ephemeral mode in P1.

## Authority

This changes isolation only. It does not widen what LOM may execute.

- autonomous ceiling: `PREPARE_PR`
- execution authority: `NONE` at the governance/profile layer
- Production authority: `HUMAN_ONLY`
- protected-main merge: `HUMAN_ONLY`
- Production credentials: `FORBIDDEN`
- Production execution: `DISABLED`
