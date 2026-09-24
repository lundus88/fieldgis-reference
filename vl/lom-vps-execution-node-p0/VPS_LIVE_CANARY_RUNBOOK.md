# VPS Live Canary Runbook — P1

Status: READY TO RUN / NON-PRODUCTION / LIVE VPS UNVERIFIED

Repository CI validates the collector, contract, resolver and fail-closed behavior. It does **not** prove the real VPS. A real PASS requires evidence generated on the authorized non-Production VPS by the dedicated unprivileged `lom-runner` identity.

## Preconditions

- explicit non-Production canary window;
- authorized operator access to the VPS;
- dedicated `lom-runner` OS user exists and is not root;
- repository checkout is at the exact intended `main` revision;
- no Production/API credentials are intentionally injected into the runner environment;
- rollback is known: stop/disable the runner and preserve evidence files.

Do not run the collector as root. Do not add the user to the Docker group or grant sudo merely to make a check pass.

## Collect live evidence

From the repository checkout, as `lom-runner`:

```bash
cd vl/lom-vps-execution-node-p0
REPO_SHA="$(git rev-parse HEAD)"
python3 collect_live_canary.py \
  --confirm-live-vps \
  --node-id openclaw-vps-01 \
  --repo-sha "$REPO_SHA" \
  --output "$HOME/lom-vps-canary-evidence.json"
```

The collector runs only registered diagnostics. It does not accept arbitrary shell, URL, token, secret or Production actions. The sudo check uses non-interactive `sudo -n true`; it never supplies credentials. Environment evidence records forbidden **key names only**, never values.

## Resolve evidence

```bash
python3 resolve_live_canary.py \
  --contract vps-canary-contract.json \
  --evidence "$HOME/lom-vps-canary-evidence.json" \
  --output "$HOME/lom-vps-canary-resolution.json"
```

Exit code:
- `0`: all required checks PASS and evidence is accepted as live VPS evidence;
- non-zero: HOLD. Do not activate the VPS adapter.

## Required checks

The evidence must prove all 13 checks:

1. `unprivileged_os_identity`
2. `sudo_denied`
3. `docker_socket_denied`
4. `production_secrets_absent`
5. `acp_allow_enforced`
6. `acp_deny_enforced`
7. `registered_health_probe_pass`
8. `production_capability_denied`
9. `connector_capability_denied`
10. `identical_replay_idempotent`
11. `changed_replay_denied`
12. `journal_restart_integrity`
13. `heartbeat_evidence_available`

Live evidence must also contain a node attestation bound to the same `node_id`, non-root UID, hashed hostname/boot identity, collector version, exact repository SHA and explicit `NON_PRODUCTION_VPS` classification. Synthetic sources cannot activate the node.

## PASS rule

Every required check must PASS. Missing, unknown, stale, mismatched, synthetic, unattributed or failed evidence means HOLD.

A PASS means only that the VPS is suitable as a bounded **non-Production** LOM execution node under this contract. It does **not** authorize connector/OpenClaw execution, Production access, Production deploy/rollback, protected-main merge, payment, pricing, legal, customer or financial commitments.
