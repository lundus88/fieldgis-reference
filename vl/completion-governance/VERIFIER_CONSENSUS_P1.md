# LOM Completion Governance P1 — Verifier Consensus & Disagreement Gate

Status: DEVELOPMENT / NON-PRODUCTION

This extends the existing independent completion validator. It does not create a second completion authority, evaluator, certifier, or execution runtime.

## Purpose

A single independent PASS remains valid for the existing base completion decision. P1 adds a high-assurance consensus path for cases where stronger verification is required.

The consensus layer can confirm a base PASS. It cannot upgrade a base HOLD or FAIL.

## Default high-assurance policy

- minimum independent validators: 2
- minimum distinct verification methods: 2
- unanimous PASS required
- duplicate validator identities: HOLD
- self-validation: HOLD
- stale verifier evidence: HOLD
- decision-digest mismatch: HOLD
- non-addressable evidence reference: HOLD
- duplicate verifier evidence references: HOLD by default
- confidence spread > 0.20: HOLD
- any validator HOLD: HOLD
- any validator FAIL: FAIL

A negative finding cannot be outvoted by additional PASS reports.

## Binding and independence

Every verifier report binds to the exact base `decision_sha256`.

Each report must include:

- validator identity
- executor identity
- exact decision digest
- PASS / HOLD / FAIL
- addressable evidence reference
- fresh-evidence flag
- calibrated confidence in [0,1]
- verification method identity

The validator identity must differ from the executor identity.

## Authority

Verifier consensus grants no execution authority.

- execution authority: NONE
- execution performed: false
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-approval: FORBIDDEN
- authority widening: DISABLED
- builder self-report trusted: false

Consensus PASS is stronger evidence, not permission to merge or deploy.

## Frontier relationship

This capability is intended to strengthen the ROBUSTNESS, EVIDENCE and GOVERNANCE dimensions of the Frontier Scorecard.

It does not self-certify a frontier improvement. Measured benchmark evidence remains required.
