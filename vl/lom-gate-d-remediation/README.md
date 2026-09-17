# LOM 2.0 Gate D — Autonomous Remediation & Recovery Loop

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #197

## Purpose
Gate D adds bounded remediation on top of the Gate C multi-agent runtime. It permits only explicitly delegated, reversible, non-production, low-risk remediation actions with attributable evidence and independent re-validation.

## Core contract
1. Detect a remediable runtime failure.
2. Classify risk and authority before any remediation.
3. Allow remediation only when action is explicitly delegated, reversible, non-production, low-risk and evidence-backed.
4. Execute one bounded remediation attempt.
5. Re-run validation independently.
6. Close only when validation proves recovery.
7. HOLD or ESCALATE when evidence is missing, retries are exhausted, risk exceeds threshold, or any HUMAN_ONLY boundary is touched.

## Recurrent failure intelligence
Gate D now includes cross-run recovery memory as an advisory-only extension. It does not create a second remediation engine and does not execute fixes itself.

The recurrent-failure layer:
- fingerprints failures using project, component, failure class, error code and environment;
- records evidence-backed recovery attempts and their independently validated outcomes;
- avoids repeating recovery actions that already failed for the same failure signature;
- prefers a previously validated known-good recovery route when the same failure recurs;
- selects an untried delegated fallback when available;
- prevents remediation loops when every bounded route has failed;
- escalates recurrent unresolved failures for human review;
- never proposes an autonomous route across the Production boundary;
- never widens the Gate D delegation envelope.

All recommendations remain `execution_authority=NONE`, `execution_performed=false`, `production_authority=HUMAN_ONLY`, with autonomous ceiling `PREPARE_PR`.

## Explicitly forbidden
- protected-main merge
- production deploy/release
- production data mutation
- authority/security-policy widening
- customer outreach
- bid submission
- quotation/pricing commitment
- contracting/legal commitment
- financial commitment
- destructive or irreversible remediation
- self-certification

Unknown authority defaults to HOLD. Remediation cannot widen its own delegation envelope.
