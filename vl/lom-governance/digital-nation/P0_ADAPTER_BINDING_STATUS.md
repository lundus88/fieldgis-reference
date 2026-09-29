# LOM Virtual World — P0 Adapter Binding Status

Status: DRAFT / NON-PRODUCTION  
Date: 2026-09-29

The binding audit distinguishes **existing reusable capability**, **new thin Preview adapters**, and **unmerged dependencies**.

| Binding | Status | Current evidence |
|---|---|---|
| Identity / authority | BOUND_PREVIEW | Existing ACP authority model on `main` |
| Business registry / entitlement | BOUND_PREVIEW | Existing LD Business Engine foundation on `main` |
| Payment confirmation | BOUND_PREVIEW | Existing payment gateway contract on `main`; provider remains non-Production |
| Affiliate / referral | BOUND_PREVIEW | Existing LD affiliate contract on `main` |
| Economic participation | HOLD_PENDING_DEPENDENCY | PR #425 refreshed to current `main`; exact-head CI PASS; still Draft/unmerged and requires explicit human approval |
| Education / skill signal | BOUND_PREVIEW | LOM Education thin evidence adapter established in PR #428 |
| Reputation | BOUND_PREVIEW | LOM Trust evidence-backed dimensional reputation adapter established in PR #428 |
| Dispute workflow | BOUND_PREVIEW | LOM Trust thin adapter composes existing LD trust/refund controls |

## Decision

**The Digital Nation adapter layer is structurally ready except for Economic Participation.**

Full Golden World execution remains **HOLD** until the Economic Participation dependency is legitimately available. The hold is intentional: PR #425 is not treated as merged or Production-ready merely to make Digital Nation appear complete.

## Resolved in this iteration

- Education/Skill now has an explicit Preview owner without creating a second LMS.
- Verified skill signals cannot be created from self-report alone.
- Reputation now has an explicit Preview owner and uses evidence-backed dimensions rather than a single opaque human score.
- Dispute handling now has a thin composed workflow with evidence, human review and appeal boundaries.
- None of these adapters grants Production authority.

## Next gate

1. PR #425 exact-head CI is now PASS after refresh and overlap cleanup; keep it Draft until explicit human approval.
2. Golden World Preview preflight is implemented and must remain HOLD while #425 is unmerged.
3. If #425 is explicitly approved and merged, require exact-main evidence before changing the binding to `BOUND_PREVIEW`.
4. Then run the complete **Golden World Journey Preview**.
5. Review privacy, security, commercial and financial boundaries.
6. Keep Production activation as a separate explicit human decision.
