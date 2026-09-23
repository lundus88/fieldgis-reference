# LOM VPS Execution Node P0

Status: REPOSITORY CANDIDATE / NON-PRODUCTION / NOT DEPLOYED

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

## Current limitation

This PR does **not** prove the real VPS is currently reachable, healthy or configured this way. There is no SSH/VPS connector available in the current control session. Deployment requires a separate VPS canary with machine-readable evidence.

## Future canary, not authorized here

A later non-Production canary should prove:

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

Until that evidence exists, status remains `REPOSITORY_CANDIDATE_ONLY`.


## BodyRuntime executor bridge

`body_executor_adapter.py` binds the canonical LOM `BodyRuntime` bounded-delegation contract to this node without introducing a second executor. Activation is fail-closed: a complete validator fixture is insufficient. The adapter requires fresh evidence classified as `LIVE_VPS_CANARY`, rejects `synthetic:*` sources, validates the canary on every invocation, accepts only registered PREPARE-level actions, requires matching ACP grant scope, and keeps Production locked. Identical requests are idempotent and return replay evidence rather than executing again.

Repository CI therefore proves code and contract behavior only. Until a real VPS produces a fresh live canary, this adapter remains **HOLD / not activated**.
