# LOM Level-6 Operational Maturity Validation

Authoritative work item: Issue #158.

This layer extends the existing LOM 5.0 operational-maturity runtime with a fail-closed, multi-project evidence evaluator. It does **not** replace LOM 5.0 and does not widen authority.

## Current evidence state

The registry intentionally records the existing Golden Workflow evidence as `PARTIAL` until every mandatory field required by Issue #158 is bound to reproducible evidence.

Current known records:

- Golden #1 — e-BKL real-world workflow with human acceptance: historical starting evidence exists, but mandatory per-run digests/budgets/metrics are not yet bound in the repository record.
- Golden #2 — e-BKL fail-closed HOLD/BLOCKED case: QA lineage and blocked behavior are recorded; mandatory per-run metrics/digests remain incomplete.
- Golden #3 — LundusLead remediation case: bounded remediation and QA evidence are recorded; mandatory per-run metrics/digests remain incomplete.
- Golden #4 — KontenStudio source recovery: deployment SHA lineage was recovered, but reproducible repository QA remains pending. The repository is visible, while `main` is not currently resolvable.
- Golden #5 — LOM Capture v2 real workflow: VERIFIED after exact-head execution, independent validation, explicit human approval on PR #352, and merge commit binding. This is the first complete VERIFIED run under Capture v2.
- Golden #6 — e-BKL fail-closed workflow: VERIFIED BLOCKED case after e-BKL rejected a prohibited official-submission claim, preserved Adjustment/Export/Submission/Production locks, passed independent validation, PR #70 approval, and merge binding.

Golden #5 and #6 now provide two VERIFIED runs across two projects. The fail-closed criterion is satisfied, but Issue #158 still requires at least four VERIFIED runs across at least three projects, including VERIFIED remediation and bounded multi-agent evidence.

Therefore the current maturity verdict is expected to remain:

`HOLD / OPERATIONAL_MATURITY_EVIDENCE_INCOMPLETE`

A PASS must never be inferred from issue prose, a successful build alone, or an incomplete historical record.

## Promotion rule: PARTIAL -> VERIFIED

A run may be promoted to `VERIFIED` only when all mandatory evidence is present:

- request ID and App Spec digest;
- context-policy digest;
- model-routing decision digest;
- capability and resource scope;
- token, cost, time and retry budgets;
- source commit and artifact hashes;
- QA/security evidence;
- independent validation;
- remediation history, including an explicit empty list when none occurred;
- release-candidate state;
- explicit human decision;
- release outcome and rollback/audit linkage;
- final outcome, attempts, elapsed time and estimated model/tool cost;
- explicit zero/non-zero flags for budget overrun, authority expansion and fabricated PASS;
- explicit production-approval and builder-self-certification flags;
- multi-agent delegation evidence.

The evaluator also requires, across the longitudinal set:

- at least 4 VERIFIED runs;
- at least 3 distinct projects;
- at least one fail-closed HOLD/BLOCKED case;
- at least one remediation case;
- at least one bounded multi-agent delegation with no authority expansion;
- zero budget overruns;
- zero authority-expansion incidents;
- zero fabricated-PASS incidents;
- no autonomous Production approval;
- no builder self-certification.

## Authority boundary

- autonomous ceiling: `PREPARE_PR`;
- protected-main merge: `HUMAN_ONLY`;
- Production deployment/release: `HUMAN_ONLY`;
- Production data mutation: `HUMAN_ONLY`;
- authority widening: `HUMAN_ONLY`;
- incomplete, contradictory or malformed evidence: `HOLD`.

`evidence_capture.py` is now the standard capture path for future Golden Workflows. It binds deterministic digests, budgets, authority scope, measured outcome evidence and the human gate before any VERIFIED promotion. Historical records remain PARTIAL unless authoritative missing facts are recovered.

`build_longitudinal_summary.py` reports the current state. Use `--require-pass` only when Issue #158 completion evidence is believed to be complete; the command must return non-zero while evidence remains incomplete.
