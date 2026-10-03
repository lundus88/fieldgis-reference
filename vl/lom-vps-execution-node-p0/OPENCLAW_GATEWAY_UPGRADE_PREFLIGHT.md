# OpenClaw Gateway Upgrade Preflight — v103067

Status: **PREPARED / READ-ONLY / NO UPDATE AUTHORITY**

Target: canonical VPS `v103067`.

This runbook exists to determine the actual OpenClaw install/version/ownership before any upgrade. It extends the existing VPS execution-node evidence path; it does not create a second runtime or authority system.

## Why this gate exists

LundusLead production has verified that both Prospect Hunter and Tender Watch reach the configured OpenClaw hook with HTTP 200, but the current Gateway response does not expose terminal completion evidence expected by the current LL integration. Do not assume the installed Gateway version or install type.

## Read-only preflight

Run as the account that owns the OpenClaw CLI/Gateway installation. Do **not** use root merely to make the checks pass.

```bash
cd /home/lom-runner/fieldgis-reference
bash vl/lom-vps-execution-node-p0/openclaw_gateway_preflight.sh
```

The script prints one local evidence directory. Review only `summary.txt` first.

Required commands captured:
- `openclaw --version`
- `openclaw update status --json`
- `openclaw update --dry-run --json`
- `openclaw health`
- `openclaw gateway status --deep --json`
- `openclaw doctor --lint --json`

No update, restart, package mutation, config mutation, firewall change, reboot, Docker change, or service ownership change is permitted by this preflight.

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
