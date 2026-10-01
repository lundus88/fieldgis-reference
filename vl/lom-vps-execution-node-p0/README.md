# LOM VPS Execution Node P0

Status: MERGED CODE / NON-PRODUCTION / LIVE VPS VERIFIED

## Purpose

Turn the existing VPS from a specialized OpenClaw host into a future persistent execution node for LOM **without** creating a second authority system.

The node is an adapter to the existing VL Agent Control Plane (ACP). ACP remains the policy authority. The node executes only after ACP returns an explicit `allow`.

## P0 execution surface

Allowed ACP capabilities are deliberately narrower than the full ACP vocabulary:

- `spec.read`
- `artifact.read`
- `qa.execute`
- `factory.plan`
- `certification.propose`
- `release.request_approval`

Supported task types are built-in and deterministic. No caller may submit a raw shell command, arbitrary URL, script, token, secret or credential.

## Explicitly disabled

P0 cannot execute:

- `production.*`
- `connector.invoke:*`, including OpenClaw
- protected-main merge
- Production deploy/promotion/rollback
- Production data mutation
- payment/charge/refund
- pricing, legal or customer commitment
- arbitrary shell or arbitrary URL fetch

OpenClaw keeps its existing controlled LundusLead integration path. It is **not** silently moved behind this node in P0.

## Canonical runtime host policy

LOM runtime execution is `VPS_ONLY` on authorized node `v103067`. Office workstations are excluded from the runtime dependency graph and cannot satisfy live-canary activation. There is no workstation execution fallback.

A human operator may administer or review the system from an approved client, but that client does not host LOM workers, queues, heartbeats, runtime secrets or execution evidence.

## Least privilege VPS target

When later deployed to the VPS, the runner must use a dedicated unprivileged OS user with:

- no root/sudo;
- no membership in the Docker group;
- no mount of `/var/run/docker.sock`;
- no host networking;
- no broad filesystem access;
- no ambient Production credentials;
- bounded CPU/memory/time budgets;
- read-only code/artifact mounts where practical.

The P0 repository code rejects known Production/API secrets in its runtime environment and rejects `DOCKER_HOST`.

## Execution flow

`LOM intent -> ACP action envelope + persisted grant -> ACP runtime allow -> VPS built-in task -> result digest -> append-only local evidence journal -> LOM evidence ingestion`

Identical replays are no-ops. Changed replays are denied by ACP. Journal tampering fails closed.

## Current live boundary

Live activation has been verified on authorized node `v103067` with machine-readable P1 canary evidence, loopback-only Secure Task Ingress, reboot recovery and the read-only operational hardening probe.

That verification is not a permanent health guarantee. Live evidence remains fail-closed and must be refreshed after relevant runtime, repository or boot changes. A stale or repository-mismatched canary, failed service recovery, public ingress exposure or weakened authority boundary returns the node to HOLD.

## Live canary, separately authorized

The non-Production live canary proves:

1. dedicated unprivileged `lom-runner` OS identity;
2. no root/sudo/Docker socket access;
3. no Production secrets in environment;
4. ACP allow/deny enforcement;
5. registered health probe executes;
6. production/connector capability attempts are denied;
7. identical replay is idempotent;
8. changed replay is denied;
9. evidence journal survives restart;
10. node heartbeat and evidence can be consumed by LOM Health & Drift.

The authorized node has satisfied this activation evidence. Future health remains dependent on fresh node-bound evidence and exact repository identity.


## BodyRuntime executor bridge

`body_executor_adapter.py` binds the canonical LOM `BodyRuntime` bounded-delegation contract to this node without introducing a second executor. Activation is fail-closed: a complete validator fixture is insufficient. The adapter requires fresh evidence classified as `LIVE_VPS_CANARY`, rejects `synthetic:*` sources, validates the canary on every invocation, accepts only registered PREPARE-level actions, requires matching ACP grant scope, and keeps Production locked. Identical requests are idempotent and return replay evidence rather than executing again.

Repository CI still proves code and contract behavior only. The adapter is live-verified only while fresh node-bound evidence remains valid; stale, missing or repository-mismatched live evidence returns it to **HOLD**.


## Machine-readable live collector

`collect_live_canary.py` gathers the 13 required checks on an explicitly confirmed non-Production VPS and emits node-bound evidence without secret values. `resolve_live_canary.py` evaluates that evidence against the canonical contract. CI or synthetic fixtures cannot activate the node because live evidence requires an explicit node attestation and `vps:<node_id>:` source binding.

The exact operator procedure is in `VPS_LIVE_CANARY_RUNBOOK.md`. A non-zero resolver exit code means **HOLD**.
