# LOM Agentic OS P2 — Eyes, Hands & Continuity Runtime

P2 adds a bounded runtime surface on top of P0 intelligence and P1 multi-model governance.

## Eyes
Read-only observation adapters emit provenance-bound observations with source, timestamp, freshness TTL and payload digest. Stale or missing observations fail closed.

## Hands
The action broker accepts only allow-listed non-Production capabilities. Every action is authority-checked, idempotency-bound, defaults to dry-run, records before/after evidence and requires post-action verification. Consequential actions remain HUMAN_GATE.

## Continuity
A durable SQLite state store persists checkpoints and an append-only event journal. Lease/heartbeat ownership prevents concurrent duplicate workers. Resume is deterministic and digest-bound to the last checkpoint.

## Explicit authority boundary
Autonomous ceiling remains PREPARE_PR.

HUMAN_ONLY:
- Production release/deploy/promotion
- Production data mutation
- protected-main merge
- customer/legal/pricing/bid/financial commitments
- credential, policy or privilege widening
- destructive data actions

Self-certification remains forbidden. P2 does not add provider credentials or live Production authority.

## Intended deployment posture
Development/non-Production first. VPS/runtime installation may bind real observation and action adapters later under least privilege, separate credentials, explicit scopes, and human release gates.
