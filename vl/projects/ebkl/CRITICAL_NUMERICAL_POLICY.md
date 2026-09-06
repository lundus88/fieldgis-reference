# e-BKL — VL Critical Numerical / Cadastral Policy

Status: BRANCH-ONLY INTEGRATION / NOT PRODUCTION

Target project: e-BKL SurveyOS — Professional Cadastral Survey Work Engine
Target repository: `lundus88/ebkl`
Default development target: governed non-production branch (currently `ebkl-cadastral-v2`)
VL project class: `CRITICAL_NUMERICAL / CADASTRAL`

## Authority model

VL may implement, refactor and test software structure, UI, workflow, state management, import/export plumbing, non-destructive QA tooling, documentation and CI for e-BKL.

VL must not independently establish cadastral truth or regulatory authority.

## Hard locks

1. No invented cadastral formula, tolerance, threshold or regulatory rule.
2. No silent numeric coercion.
3. CRS/datum must be explicit.
4. No automatic movement, reconciliation or acceptance of a cadastral boundary conflict.
5. Any boundary evidence conflict must resolve to `HUMAN_REVIEW_REQUIRED` until a qualified human resolves it.
6. Supplemental and comparison-only fixtures may support diagnostics but cannot satisfy the authoritative Golden gate.
7. Original/verified numerical behaviour must be frozen before any numerical refactor.
8. Numerical correctness takes precedence over UI/cosmetics.
9. AI may detect anomalies but may not select cadastral acceptance thresholds or authorize acceptance.
10. VL may prepare development commits and pull requests only. Automatic merge to `lundus88/ebkl` main is prohibited.
11. VL may not deploy or mutate e-BKL production automatically.
12. Official/submission-ready exports remain blocked unless the e-BKL release gate explicitly passes.

## Minimum build gates for every VL-generated e-BKL change

- Product alignment contract valid.
- e-BKL authoritative branch accessible.
- e-BKL local/CI test suite passes for the proposed change.
- Syntax/build checks pass.
- Existing numerical and governance tests remain unchanged unless an evidence-backed change is explicitly approved.
- Golden Regression status is reported accurately; `BLOCKED` must never be relabeled as `PASS`.
- Any boundary conflict remains fail-closed.
- Release/production controls remain human-controlled.

## Production release requirements

VL does not possess production release authority for e-BKL. Release requires all relevant e-BKL gates plus explicit human approval. At minimum:

- authoritative Golden Regression PASS;
- QA gate PASS;
- CRS/datum confirmed;
- boundary review resolved;
- verified regulatory/tolerance provenance where applicable;
- explicit human production approval.

If any requirement is unresolved, release state remains `HOLD` / `BLOCKED`.
