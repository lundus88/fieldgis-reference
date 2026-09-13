# LOM 4.0 Evolution Program

Status: DEVELOPMENT / NON-PRODUCTION
Tracking: Issue #197
Baseline: `1513324aa2b37662b964239936097d4da37ce9bb`

## Mission
Evolve the existing Lundus Operating Model from governed AI operations into an Autonomous Digital Organization without weakening existing evidence, authority, segregation-of-duties, or fail-closed controls.

## Version ladder

### LOM 2.0 — Autonomous Multi-Agent Operations
Adds bounded delegation, goal contracts, deterministic plan/dependency graphs, agent-role contracts, independent verification, and exception escalation.

### LOM 3.0 — AI Business Operating System
Adds portfolio KPI/ROI observation, advisory prioritisation, operating scorecards, institutional memory, and cross-project learning. Financial and contractual commitments remain human-only.

### LOM 4.0 — Autonomous Digital Organization
Adds an organization constitution, department/agent operating graph, autonomy maturity model, continuity/incident handling, board/director exception routing, and bounded self-remediation for non-consequential actions only.

## Constitutional invariants
1. Unknown authority defaults to `DENY_OR_HOLD`.
2. Missing or contradictory required evidence cannot produce `PASS`.
3. Builder/implementer cannot be the sole certifier of consequential work.
4. Delegated authority may stay equal or narrow; it may never widen itself.
5. Production release/deployment, protected-main merge, production data mutation, authority/security-policy widening, customer outreach, bid submission, quotation/pricing commitment, contracting/legal commitment, and financial commitment remain `HUMAN_ONLY`.
6. Self-remediation is permitted only for explicitly delegated, reversible, non-production, non-consequential scope.
7. Every material state transition must record actor, timestamp, provenance, decision, and evidence references.
8. Learning may recommend policy changes but may not auto-apply authority, scoring, threshold, financial, legal, or production changes.

## Delivery gates
- **Gate A — Foundation:** constitution, autonomy envelope, role registry, validator and adversarial tests.
- **Gate B — LOM 2.0:** bounded planner/executor/validator loop proven on non-production workloads.
- **Gate C — LOM 3.0:** portfolio economics and institutional-memory layer proven advisory-only.
- **Gate D — LOM 4.0:** organization graph, continuity engine and bounded self-remediation proven without authority widening.
- **Gate E — Release Candidate:** exact-head CI evidence and human approval required before merge.

No production activation is authorized by this package.