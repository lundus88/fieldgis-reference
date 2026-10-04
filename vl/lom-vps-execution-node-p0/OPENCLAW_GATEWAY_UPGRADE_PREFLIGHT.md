# OpenClaw Gateway Upgrade Preflight — v103067

Status: **PREPARED / READ-ONLY / NO UPDATE AUTHORITY**

Target: canonical VPS `v103067`.

This runbook exists to determine the actual OpenClaw install/version/ownership before any upgrade. It extends the existing VPS execution-node evidence path; it does not create a second runtime or authority system.

## Why this gate exists

LundusLead production has verified that both Prospect Hunter and Tender Watch reach the configured OpenClaw hook with HTTP 200, but the current Gateway response does not expose terminal completion evidence expected by the current LL integration. Do not assume the installed Gateway version or install type.

## Verified canonical runtime ownership

Fresh read-only evidence from `v103067` on 2026-10-04 established:

- verified runtime owner is `server`;
- verified CLI path is `/home/server/.npm-global/bin/openclaw`;
- the user systemd unit is `/home/server/.config/systemd/user/openclaw-gateway.service`;
- the Gateway is loopback-bound at `ws://127.0.0.1:18789`;
- runtime/Gateway version evidence reported `2026.9.7`;
- Gateway RPC recovered to `ok: true` after controlled service start;
- plugin version drift reported no drift.

The repository checkout ownership is separate from OpenClaw runtime ownership. Do not chown, migrate, duplicate, or reinstall OpenClaw merely to make this preflight run from another account.

## Read-only preflight

Run as the account that owns the OpenClaw CLI/Gateway installation. On canonical `v103067`, that account is currently `server`. Do **not** use root merely to make the checks pass.

Use the verified binary explicitly so PATH differences cannot produce a false `OPENCLAW_NOT_FOUND` result:

```bash
OPENCLAW_EXPECTED_USER=server \
OPENCLAW_BIN=/home/server/.npm-global/bin/openclaw \
bash /path/to/fieldgis-reference/vl/lom-vps-execution-node-p0/openclaw_gateway_preflight.sh
```

A readable repository checkout may remain owned by another non-root execution account. Source checkout ownership must not be confused with Gateway runtime ownership.

The script prints one local evidence directory. Review only `summary.txt` first.

Required commands captured:
- `openclaw --version`
- `openclaw update status --json`
- `openclaw update --dry-run --json`
- `openclaw health`
- `openclaw gateway status --deep --json`
- `openclaw doctor --lint --json`

No update, restart, package mutation, config mutation, firewall change, reboot, Docker change, or service ownership change is permitted by this preflight.

A non-zero command result is evidence, not permission to repair automatically. In particular, `doctor --lint` warnings must be reviewed before any `doctor --fix`, service stop/restart, scope change, or configuration mutation.

## Decision gate

**PASS to update planning only** when all are known:
1. installed OpenClaw version;
2. install owner/method;
3. update channel/target;
4. dry-run reports a supported update path;
5. current Gateway health is known;
6. Doctor does not report a blocking migration/config/plugin problem;
7. rollback/backup procedure matches the detected install type.

If any item is unknown, return **HOLD**.

## Before any actual update

Follow the official OpenClaw update guidance for the detected installation type.

Mandatory:
- create a verified pre-update backup;
- retain the exact current package/source version;
- retain current config/state recovery material;
- do not combine the OpenClaw update with OS, firewall, Node, plugin, DNS, proxy, or unrelated service changes;
- keep LOM Production authority and connector boundaries unchanged.

For a supported managed install, preview first:

```bash
openclaw update --dry-run --json
```

Only after human review of that result may an actual `openclaw update` be considered.

For Docker/Podman/Kubernetes, use the installation owner's image replacement path rather than `openclaw update`.

## Post-update acceptance

After any approved update:
1. `openclaw --version`;
2. `openclaw doctor`;
3. `openclaw health`;
4. `openclaw gateway status --deep --json`;
5. verify the Gateway listener/ownership has not widened;
6. re-run LundusLead `Pools -> Cari kedua-dua trek sekarang` once;
7. require terminal completion/callback evidence for both OpenClaw Prospect Hunter and Tender Watch;
8. keep PR #181 on HOLD until both LL acquisition tracks are evidenced.

## Stop conditions

Immediate HOLD if:
- install type/version cannot be established;
- backup cannot be verified;
- update dry-run reports refusal or migration/plugin blockers;
- Gateway health is already degraded;
- update would require unrelated host changes;
- service ownership changes unexpectedly;
- public ingress or Production authority widens;
- callback/acquisition evidence remains absent after post-update verification.
