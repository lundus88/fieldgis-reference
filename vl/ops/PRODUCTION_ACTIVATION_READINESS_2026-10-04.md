# VL Production Activation Readiness — 2026-10-04

Status: **HOLD / NOT READY FOR PRODUCTION ACTIVATION**  
Authority: HUMAN_ONLY  
Scope: certification-health operational contracts only. Repository readiness does not authorize Production DDL, health finalization, release approval, promotion, or deployment.

## Live read-only audit

Production project: `vrs-core` (`wczelfmnqpgzfdszxubl`)

### Green evidence

- Supabase project status: `ACTIVE_HEALTHY`.
- Active builders: 5.
- Active certification policies: 5.
- Latest result for every active builder:
  - decision `certified`;
  - score `1.0`;
  - distinct run count `4`;
  - no missing evidence.
- Every active builder has a complete PASS evidence set bound to a staging-targeted, production-locked, awaiting-approval factory run.
- Release-validation queue: 0.
- One common owner/admin actor covers all five selected projects.
- Existing Production rollback pipeline is present.
- Historical real rollback rehearsal succeeded with post-rollback verification PASS.

## Current blockers

### 1. Effective-health freshness — RED

The effective-health contract defaults to **1,800 seconds / 30 minutes**.

Current reviewed evidence set has:

- evidence floor: `2026-10-03T21:40:26.150556Z`;
- latest selected evidence: `2026-10-04T01:12:21.119696Z`.

The finalizer deliberately writes the **oldest selected evidence timestamp**, never wall-clock time. Therefore current evidence would remain stale even if finalized.

**Required:** a genuine fresh certification/evidence set for all active builders immediately before authorization/finalization.

### 2. AAL2 human authorization — RED

Read-only Auth aggregate:

- total MFA factors: 0;
- verified MFA factors: 0.

No existing repository producer for `vl.cert_health_finalization_authorized` was present before this hardening.

**Required:** verified human MFA/AAL2 before any certification-health authorization can be consumed.

### 3. Production DDL — RED

At audit time these functions were absent from Production:

- `private.finalize_vl_cert_health_from_fresh_certification(...)`;
- `public.get_vl_cert_health_effective(integer)`;
- `public.vl_reconcile_stale_factory_workflow(...)`.

Repository merge is not Production deployment authority.

### 4. Backup / restore evidence — RED

The continuity policy requires:

- current backup freshness evidence;
- tested restore evidence;
- explicit human authority for destructive restore/failover.

Available project tooling does not expose current backup freshness or a tested restore for this exact activation. This remains a human/operator evidence requirement.

## Operational debt — AMBER

At audit time:

- factory runs `awaiting_approval`: 31;
- approvals `pending`: 30;
- queued/claimed/running release-validation jobs: 0.

This is degraded operational debt, not automatic Production authority.

## Production-deployment provenance finding

All five selected evidence-producing factory runs have a deployment row bound to a logical Production environment. The rows are not live deployments:

- status = `certified`;
- `approved_by IS NULL`;
- `deployed_at IS NULL`.

The finalizer is nevertheless hardened in this branch to reject any selected evidence run when a Production deployment has real authority/effect:

- status in `approved/deploying/deployed`; or
- `approved_by IS NOT NULL`; or
- `deployed_at IS NOT NULL`.

## Hardening introduced by this branch

### Human authorization producer

`public.authorize_vl_cert_health_finalization(...)`

Properties:

- authenticated human only;
- AAL2 required;
- explicit reason required;
- SHA-256 evidence digest required;
- owner/admin membership required;
- authorization expires after 15 minutes;
- duplicate unconsumed authorization is idempotently reused;
- creates audit intent only;
- cannot update health, certification evidence, approvals, deployments or lifecycle state.

The finalizer independently recomputes evidence, digest, project scope, freshness and replay status. Authorization is not self-certification.

### Effective-health freshness lock

The finalizer now refuses to update `public.vl_cert_health` when the oldest selected evidence is older than 1,800 seconds.

Failure reason:

`EVIDENCE_TOO_OLD_FOR_EFFECTIVE_HEALTH`

### Production-authority exclusion

The finalizer refuses selected evidence from a run with actual Production authority/effect.

Failure reason:

`SELECTED_EVIDENCE_RUN_HAS_PRODUCTION_AUTHORITY`

### Forward migration

`vl/migrations/20261004154500_cert_health_activation_hardening.sql`

- DDL only;
- materializes the exact reviewed reconciliation, freshness and authorization/finalization contracts;
- does not refresh health or mutate lifecycle data.

### Reverse migration

`vl/ops/rollback_cert_health_activation_20261004.sql`

- drops only functions introduced by the forward migration;
- does not rewrite health timestamps;
- does not delete audit evidence;
- does not mutate factory runs, workflows, approvals, deployments or certification evidence.

## Required validation sequence

1. Exact-head CI GREEN.
2. Independent human PR review.
3. Create isolated data-less DEV branch with explicit cost approval.
4. Apply canonical baseline recovery if native legacy replay fails.
5. Apply the forward migration on DEV.
6. Run security/performance advisors.
7. Test:
   - no MFA/AAL2;
   - wrong digest;
   - stale authorization;
   - authorization-before-evidence;
   - owner/admin scope mismatch;
   - replay;
   - evidence older than 30 minutes;
   - production-approved/deployed evidence run;
   - successful fresh-evidence candidate.
8. Run reverse migration on DEV.
9. Verify schema returns to the pre-forward fingerprint and runtime rows remain unchanged.
10. Re-apply forward migration on DEV and repeat critical fail-closed tests.
11. Verify backup freshness and tested restore evidence through the authorized Supabase operator path.
12. Enrol/verify human MFA.
13. Trigger a genuine fresh certification run for all active builders.
14. Compute a new evidence digest from evidence <30 minutes old.
15. Create AAL2 human authorization bound to the exact run window/digest.
16. Separate human gate for Production DDL.
17. Post-deploy read-only verification.
18. Separate human gate for certification-health finalization.

## Explicitly not authorized

- Production DDL deployment;
- Production health refresh/finalization;
- Production approval or promotion;
- Production release;
- bulk approval cleanup;
- synthetic certification PASS evidence;
- timestamp refresh without genuine current evidence.

Principle: **Stabilize → Prove → Scale.**


## 2026-10-05 readiness refresh

Read-only verification after builder certification closure:

- builder certification phase is formally **GREEN** with 5/5 builders certified, score 1.0 and zero missing evidence;
- GIS and Mobile fresh certification completed successfully, including Mobile Android emulator GPS/device E2E;
- Supabase Auth now has **1 MFA factor / 1 verified MFA factor**; this proves enrollment exists, but the operator must still establish an **AAL2 session at authorization time**;
- `public.vl_cert_health` still carries the historical 2026-08-25 timestamp, so authoritative health freshness remains **HOLD** until the reviewed finalizer is deployed and a new fresh certification window is authorized;
- all current pending production-release approvals remain production-locked; dry-run reconciliation found no approval eligible for automatic stale expiry under the existing contract;
- the previously missing managed Realtime relations in `vl-api-production` are present again and the sampled recent log window showed no `realtime.subscription` missing-relation errors; a controlled end-to-end Realtime/Postgres Changes test is still required before Issue #446 can close.

This refresh does not authorize Production DDL, health finalization, release approval, promotion or deployment.
