# LOM VPS Operational Hardening — P0

Status: PREPARED / NON-PRODUCTION / NO NEW AUTHORITY

Target node: `v103067`

This hardening layer extends the existing **LOM System Health & Drift P0** surface. It does not create a second health engine, alerting platform, worker, scheduler, recovery engine, or Production authority path.

## Objectives

Keep the canonical always-on VPS observable and recoverable without weakening the existing boundaries:

- `lom-worker.service` remains enabled and active;
- `lom-heartbeat.timer` remains enabled and active;
- `lom-secure-ingress.service` remains enabled and active;
- Secure Task Ingress remains loopback-only and reports `READY`;
- `production=false` and `production_locked=true` remain mandatory;
- a fresh live VPS canary remains `PASS`;
- disk free space remains above the P0 floor of 15%;
- Production authority remains `HUMAN_ONLY`.

## Read-only operational probe

Run as `lom-runner`:

```bash
cd /home/lom-runner/fieldgis-reference/vl/lom-system-health-p0
python3 vps_operational_probe.py
```

Exit behavior:

- `0`: `HEALTHY`;
- `2`: `HOLD`.

The probe performs no remediation. It only reads systemd state, the loopback ingress health endpoint, the live-canary resolution file and local disk usage.

## Alerting integration

Do not introduce a second alerting product.

A non-zero probe result is an operational signal that can be routed into the existing LOM health/drift and governed alerting surfaces. External notifications require an already approved connector or alerting path. The probe itself sends nothing externally and stores no credentials.

Recommended conditions for notification:

- any required service is not active or not enabled;
- ingress is not `READY`;
- Production lock is weakened;
- live canary is unavailable or not `PASS`;
- disk free space falls below 15%.

## Log retention

The canonical services log to systemd journal. Do not add duplicate per-service logfile pipelines unless a later evidence requirement specifically needs them.

Operational policy:

- use `journalctl -u <unit>` for incident diagnosis;
- bound journal growth using the host's journald retention policy;
- do not delete live evidence during an incident;
- preserve relevant journal slices and canary resolution before remediation.

Any host-level journald retention change is an administrative operation and must be reviewed before deployment.

## Evidence backup

The canonical evidence artifacts are:

- `/home/lom-runner/lom-vps-canary-evidence.json`
- `/home/lom-runner/lom-vps-canary-resolution.json`
- ingress `/health` response;
- relevant systemd journal slice;
- exact repository SHA.

For consequential incidents, copy the evidence package to an approved durable evidence store before changing runtime state. Do not copy secrets such as the ingress HMAC key.

## Recovery SOP

1. **Observe** — run the operational probe and capture exact SHA.
2. **Classify** — HEALTHY vs HOLD; do not infer health from a single service state.
3. **Preserve evidence** — canary resolution, health JSON and journal slice.
4. **Bound the fix** — restart only the affected non-Production service when evidence supports it.
5. **Verify** — service active, ingress loopback-only, health READY.
6. **Re-run live canary** — 13/13 must PASS on the current boot/revision.
7. **Escalate** — Production changes, credential widening, public ingress exposure, destructive recovery or provider actions remain HUMAN_ONLY.

## Stop conditions

Immediately HOLD if:

- ingress binds to anything other than `127.0.0.1`;
- `production_locked` is false;
- a required service fails to recover;
- live canary is stale, unavailable or not PASS;
- disk free space is below the floor;
- secrets appear in logs/evidence;
- recovery would require widening runtime authority.

## 24/7 interpretation

A successful reboot/recovery test proves **operational readiness for always-on execution**, not a mathematical guarantee of uninterrupted availability. Provider, network, kernel or infrastructure outages remain possible and must be handled through monitoring, evidence and recovery procedures.
