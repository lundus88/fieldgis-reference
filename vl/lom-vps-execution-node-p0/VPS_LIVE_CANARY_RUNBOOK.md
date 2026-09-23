# VPS Live Canary Runbook — P0

Status: NOT RUN / NON-PRODUCTION

This runbook is the future evidence procedure for the real VPS. Repository CI validates the canary **contract and validator only**. Synthetic fixtures are never evidence that the VPS itself passed.

## Preconditions

- explicit non-Production canary window;
- VPS access available through an authorized operator/tool;
- dedicated unprivileged `lom-runner` user prepared;
- no Production credentials exposed to the runner;
- ACP evidence source available;
- known rollback: disable/stop the runner service and preserve journal.

## Required live evidence

Capture every check in `vps-canary-contract.json` with a machine-readable source reference and timestamp.

Required observations:

1. `id -u` proves the runner is not root.
2. sudo attempt is denied.
3. Docker socket access is denied and runner is not in Docker group.
4. environment inventory proves Production/API secrets are absent; record key names only, never secret values.
5. one registered staging action is explicitly allowed by ACP.
6. one invalid/ungranted action is denied by ACP.
7. built-in health probe passes.
8. `production.*` request is denied.
9. `connector.invoke:*` request is denied in P0.
10. identical action replay returns idempotent no-op.
11. changed replay is denied.
12. restart runner and verify journal hash-chain integrity.
13. capture node heartbeat evidence.

## PASS rule

Every required check must be PASS. Missing, unknown, stale, unverifiable or failed checks mean HOLD.

## What a PASS would mean

A PASS would establish that the VPS is suitable as a bounded non-Production LOM execution node under the P0 contract.

It would **not** authorize:
- connector/OpenClaw execution through the node;
- Production access;
- Production deployment or rollback;
- protected-main merge;
- payment, customer, legal or financial actions.

Those require separate later phases and human authority.
