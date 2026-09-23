# LOM CAIE P0.1 — Evidence Integrity Hardening

Status: DEVELOPMENT / NON-PRODUCTION  
Tracking: Issue #375

CAIE P0.1 hardens the P0 autonomous-improvement boundary without widening authority.

Canonical flow remains:

`Observe → Diagnose → Plan → Sandbox → Test → Score → Remediate → Certify → PREPARE_PR`

## What P0.1 adds

1. **Signed evidence records**
   - HMAC-SHA256 signature over canonical evidence metadata.
   - Mandatory evidence kind, issuer, subject, provenance, issued/expiry time and payload digest.
   - Qualification, trigger, evaluation, baseline, usage and certification evidence all fail closed.

2. **Freshness and provenance checks**
   - stale, expired, future-dated, malformed or wrong-subject evidence cannot PASS.
   - provenance must be an attributable URI/URN-style reference.
   - evaluation/baseline/usage/certification payloads are bound to their signed SHA-256 digest.

3. **Independent certification evidence**
   - certification is no longer a pair of caller booleans.
   - certifier identity must match the assigned independent certifier.
   - certification evidence issuer must be the certifier.
   - builder self-certification remains forbidden.

4. **Tamper-evident state ledger**
   - state transitions are constrained by an explicit transition graph.
   - each transition is chained with an engine-private HMAC digest.
   - direct state mutation or history tampering cannot produce `PREPARE_PR`.
   - certification generates an engine-bound token tied to the certified ledger tail.

5. **Exact-main verification**
   - CAIE CI runs on pull requests and on pushes to `main`.
   - pull requests test the exact PR head SHA.
   - post-merge runs test the exact main commit SHA.

## Key handling boundary

P0.1 contains no Production evidence key. The runtime requires a key to be injected by its caller. The repository contains only deterministic test keys in unit tests.

For any future Production-capable implementation:
- retrieve evidence-signing material from an approved secret manager;
- never store live signing material in source control;
- separate issuer/signing authority from builder authority;
- rotate and audit signing material;
- keep Production release authority HUMAN_ONLY.

## Authority remains unchanged

CAIE P0.1 MUST NOT:
- merge protected `main`;
- deploy or release Production;
- mutate Production data;
- widen authority;
- change critical auth/security policy;
- make customer, bid, pricing, contract, legal or financial commitments;
- delete protected data.

Autonomous ceiling remains `PREPARE_PR`.

## Regression coverage

The P0.1 suite verifies, among other cases:
- happy path stops at PREPARE_PR;
- Production and HUMAN_ONLY targets escalate;
- stale/expired/forged evidence holds;
- malformed provenance holds;
- evaluation digest mismatch holds;
- budget overrun rejects;
- missing baseline holds;
- certifier mismatch and wrong-key certification hold;
- direct state mutation cannot prepare a PR;
- transition-ledger tampering cannot prepare a PR;
- certification cannot be transferred across engine instances;
- remediation is bounded;
- protected-main merge and Production deploy remain HUMAN_ONLY.

Run:

`python vl/lom-continuous-improvement/test_caie.py`
