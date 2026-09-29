# LOM Level 8 P3 — Causal Memory Adapter

Status: DEVELOPMENT / NON-PRODUCTION / READ-ONLY PROJECTION

## Objective

Add evidence-backed causal memory to the merged LOM World State Graph without creating a competing memory store.

P3 answers a narrower question than ordinary history:

> Given a decision/action and an observed outcome, what causal lesson is independently supported by evidence?

P3 does **not** infer causality from sequence, timestamp proximity, correlation, or model opinion.

## Canonical inputs

P3 composes existing canonical records:

- Level 8 P2 World State Graph;
- Operational Safety AppendOnlyEventLedger;
- LOM 4.2 DecisionCorpus records;
- Gate D RecurrentFailureMemory FailureSignal / RecoveryAttempt records.

P3 stores nothing. It emits a deterministic read-only projection.

## Causal rules

### Decision → Action → Outcome → Cause → Lesson

A decision causal record is admitted only when:

- world graph is valid and READY;
- event-ledger hash chain verifies;
- decision_id is registered and unique;
- explicit causal binding references the exact ledger event hash;
- binding project/objective matches the world graph and ledger event;
- ledger action matches the decision action;
- causal evidence references are present;
- causal binding was independently validated;
- causal confidence is finite and in range [0,1].

Sequence alone is never causality.

### Failure → Recovery → Lesson

A recovery lesson is admitted as known-good only when:

- FailureSignal is valid and NON_PRODUCTION;
- RecoveryAttempt references the exact computed failure fingerprint;
- outcome is RECOVERED;
- recovery evidence is present;
- recovery was independently validated.

FAILED / HOLD / ESCALATE attempts remain historical evidence and are not promoted as known-good recovery lessons.

## Authority invariants

- autonomous ceiling: PREPARE_PR
- execution authority: NONE
- Production authority: HUMAN_ONLY
- protected-main merge: HUMAN_ONLY
- self-approval: FORBIDDEN
- database mutation: DISABLED
- connector execution: DISABLED
- memory persistence: NONE

## Non-duplication

P3 does not replace Event Ledger, DecisionCorpus, Recovery Memory, Project State Truth, Evidence Fabric, Operational Twin, or World State Graph.

It is an evidence-bound causal projection only.
