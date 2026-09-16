# LOM 6.10 — Project State Truth Layer

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: establish a canonical portfolio truth layer that binds every observed project status to immutable evidence provenance and the existing append-only operational event ledger.

## Why this exists
LOM already has Director Mission Control, evidence maturity checks, portfolio telemetry, an append-only event ledger, evidence lineage, approval receipts and a human-only Production boundary. The missing link is a single deterministic state derivation layer that prevents a project from being reported as VERIFIED, APPROVED or RELEASED unless the claim is backed by current, scope-correct, non-contradictory, ledger-bound evidence.

This component does not replace any existing evidence or ledger subsystem. It composes them.

## Core guarantees
- project/objective scope binding for every evidence record;
- evidence IDs are immutable; conflicting reuse is rejected;
- stale, contradictory, missing or unregistered evidence => HOLD;
- evidence must reference an existing append-only ledger event hash;
- invalid ledger integrity => HOLD;
- VERIFIED/APPROVED/RELEASED require independent validation evidence;
- APPROVED/RELEASED require explicit human-approval evidence;
- Production RELEASED may be observed only after human approval is evidenced;
- dependency HOLD/FAIL propagates fail-closed;
- deterministic portfolio snapshot fingerprint;
- duplicate conflicting project observations => HOLD.

## Authority boundary
This layer is observational only.

- autonomous ceiling: `PREPARE_PR`;
- execution authority: `NONE`;
- protected-main merge: `HUMAN_ONLY`;
- Production authority: `HUMAN_ONLY`;
- self-approval: forbidden;
- no Production deployment, release, data mutation or financial commitment;
- missing or unknown evidence/authority => HOLD.

A `RELEASED` state is therefore a verified statement about evidence already produced by an authorized human-governed process. It is never authority to perform a release.

## Intended integration
The next integration step is to feed the Project State Truth snapshot into Director Mission Control as the canonical per-project truth source, while preserving Mission Control's existing backward-compatible contracts.
