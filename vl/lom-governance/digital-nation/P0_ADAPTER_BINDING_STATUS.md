# LOM Virtual World — P0 Adapter Binding Status

Status: DRAFT / NON-PRODUCTION  
Date: 2026-09-29

The first binding audit intentionally distinguishes **existing reusable capability** from **unproven or unresolved capability**.

| Binding | Status | Current evidence |
|---|---|---|
| Identity / authority | BOUND_PREVIEW | Existing ACP authority model on `main` |
| Business registry / entitlement | BOUND_PREVIEW | Existing LD Business Engine foundation on `main` |
| Payment confirmation | BOUND_PREVIEW | Existing payment gateway contract on `main`; provider still unbound |
| Affiliate / referral | BOUND_PREVIEW | Existing LD affiliate contract on `main` |
| Economic participation | HOLD_PENDING_DEPENDENCY | PR #425 is open; not treated as merged capability |
| Education / skill graph | HOLD_UNRESOLVED_OWNER | No authoritative runtime owner proven in inspected repos |
| Reputation runtime | HOLD_UNRESOLVED_OWNER | Event contract exists, runtime owner not yet proven |
| Dispute workflow | PARTIAL_PREVIEW | Existing fraud/dispute controls are reusable but incomplete |

## Decision

**P0 integration remains HOLD for full Golden World execution.**

This is a healthy hold: it prevents the architecture from claiming capabilities that are not yet proven.

## Next actions

1. Keep PR #425 separate; do not merge it merely to satisfy Digital Nation.
2. Establish an authoritative owner for Education/Skill signals.
3. Establish an authoritative owner for evidence-backed Reputation.
4. Define the thin dispute adapter that composes existing LD trust/refund/fraud controls.
5. Once those gaps are resolved, rerun binding guard and Golden World CI.
6. Only then build a Preview end-to-end journey. Production remains separately human-gated.
