# LOM CAIE P1 — Persistent Autonomous Improvement Runtime

Status: DEVELOPMENT / NON-PRODUCTION  
Tracking: Issue #380  
Predecessor: CAIE P0.1 / Issue #375

CAIE P1 adds a persistent orchestration layer around the governed CAIE boundary.

Canonical operating loop:

`Event → Task Board → Execute → Validate → Score → Remediate (bounded) → Certify → PREPARE_PR`

## P1 capabilities

### Persistent run ledger
- append-only JSONL record
- monotonic sequence numbers
- keyed HMAC-SHA256 hash chain
- sealed sidecar head checkpoint to detect suffix/tail truncation
- fsync on append and atomic head-seal replacement
- startup verification before use
- malformed, reordered, deleted, modified, tail-truncated or wrong-key records fail closed

The repository contains no Production ledger key. Runtime callers must inject integrity material.

The file reference implementation is intentionally **single-writer**. Concurrent multi-process writers require a future datastore/locking adapter; P1 fails closed rather than claiming safe distributed writes.

### Durable task board
The board is reconstructed from the ledger rather than trusted in-memory state. Process restart can recover task state, remediation-attempt count, role assignments and authority classification.

Task states:

`QUEUED → ACTIVE → VERIFYING → REMEDIATING → VERIFYING → SCORED → CERTIFIED → PREPARE_PR`

Terminal safety states remain `HOLD`, `REJECT` and `ESCALATE`.

### Event trigger router
P1 accepts only evidence-linked, reversible, non-Production improvement events with known target/risk classes.

Supported trigger classes:
- MANUAL
- SCHEDULE
- EVENT
- CI_FAILURE
- OBSERVABILITY_ALERT

External event IDs are idempotent across process restarts. A previously accepted or rejected event is not processed twice. Task creation is persisted before the acknowledgement event so a crash in that narrow window can still be recognized as already accepted on restart.

### Scorer registry
Named scorers have:
- a threshold;
- a positive weight;
- optional hard-gate semantics.

A hard-gate failure blocks advancement regardless of weighted average. Invalid/NaN scorer output and scorer exceptions fail closed.

### Bounded autonomous remediation
P1 may retry only reversible work in a non-Production branch scope.

The initial attempt is followed by at most the configured number of remediation attempts. Every attempt requires:
- attributable evidence;
- non-Production scope;
- reversibility;
- independent validation.

Scoring or validation failure can trigger remediation only while budget remains.

### Separation of duties
Builder, validator and certifier identities must be distinct. Validation evidence and certification evidence are required before PREPARE_PR.

## Authority boundary

P1 does not grant authority to:
- merge protected `main`;
- deploy or release Production;
- mutate Production data;
- widen authority or critical security policy;
- contact customers autonomously;
- submit bids;
- commit pricing/quotations;
- enter contracts/legal commitments;
- make financial commitments;
- execute destructive or irreversible remediation.

Autonomous ceiling remains exactly:

`PREPARE_PR`

A release-candidate ledger event explicitly records:
- `merge_executed = false`
- `production_deployed = false`
- `production_locked = true`

## Persistence model

The file-backed ledger is P1's deterministic reference implementation. It proves restart/recovery and chain integrity without introducing a database or external service dependency.

A later adapter may bind the same ledger contract to an approved durable datastore, but that must not weaken:
- append-only semantics;
- chain verification;
- idempotency;
- authority boundaries;
- human Production gates.

## P1 acceptance

Run:

`python vl/lom-continuous-improvement/test_caie_p1.py`

CI must test the exact pull-request head and every push to `main`.

P1 is complete only when the regression suite proves:
- event idempotency;
- ledger tamper and tail-truncation detection;
- restart recovery and crash-window event idempotency;
- task-state enforcement;
- scorer hard gates;
- bounded remediation;
- role separation;
- Production boundary enforcement;
- successful flow stops at PREPARE_PR.
