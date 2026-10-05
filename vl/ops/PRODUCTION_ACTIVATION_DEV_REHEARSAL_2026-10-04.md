# VL Production Activation DEV Rehearsal — 2026-10-04

Status: **TECHNICAL DEV REHEARSAL PASS**  
Production activation: **HOLD**  
Production mutation performed: **NO**

## Temporary branch

- Supabase project: `vrs-core`
- Parent ref: `wczelfmnqpgzfdszxubl`
- DEV branch: `vl-prod-activation-rehearsal-20261004`
- DEV ref: `kxkchmpdhezjytqiwqaj`
- Branch id: `4e42d53c-57dc-428e-97cf-78abb9915257`
- Data mode: data-less
- Cost rate approved: USD 0.01344/hour
- Branch deleted after rehearsal: **YES**

## Native replay

Native fresh replay remained historically incomplete:

- migration count: 44
- last migration: `20260826005340`
- functions: 32
- columns: 349
- constraints: 159
- indexes: 101
- policies: 81
- `public.vl_cert_health`: absent

The canonical baseline recovery path was therefore required.

## Canonical recovery

The reviewed baseline was applied, then DEV-only migration tracking was synchronized to the exact authoritative Production history.

Before activation migration rehearsal, DEV and Production matched exactly:

- migrations: 174
- migration history SHA-256:
  `1099e33d3b2e7125e1dee037572e46ae8da390497660e10f70322ec19116949e`
- functions: 128
  - SHA-256 `c0039e155f51f93c5a9fcef7c4251258619304e39bb5f7ea3f7fc8fc3d815052`
- columns: 821
  - SHA-256 `6d1153db96f7876c9d35268e7ae9ba44650e2103caab3bf9764d8ad115e5b5b0`
- constraints: 346
  - SHA-256 `2bc9f84ec91eaa5a637a0ff0ec2fe78bb29953c197c3a98222f4bdfaefb3bd79`
- indexes: 215
  - SHA-256 `3d2ad7e49f14c6b795924f99c8426ad7300b7090b3ebfcd7e9db68e0a5968dc7`
- policies: 88
  - SHA-256 `248e901bfa38e4709d6f53febe1ef06f22458f7331da77f6d5be6cbfa082d91a`

## Forward migration rehearsal

Candidate migration:

`vl/migrations/20261004154500_cert_health_activation_hardening.sql`

The first forward rehearsal exposed one Supabase Security Advisor warning:
`authenticated_security_definer_function_executable`.

The authorization path was then hardened to:

`public SECURITY INVOKER facade`
→ `private insert-only security-invoker view`
→ `non-client-executable private SECURITY DEFINER trigger`.

After hardening:

- Security Advisor: INFO-only
- `rls_enabled_no_policy`: INFO 34
- no WARN / ERROR blocker
- public authorizer:
  - anon execute: false
  - authenticated execute: true
  - service_role execute: false
- private privileged authorization helper:
  - authenticated execute: false
  - service_role execute: false
- private finalizer:
  - anon/authenticated execute: false
  - service_role execute: true

## Fail-closed regression

All database fixtures were synthetic and wrapped in transactions that were rolled back.

### Authentication / authorization

PASS:

- no authenticated identity → rejected;
- AAL1 → rejected;
- AAL2 without owner/admin scope → rejected;
- AAL2 with owner/admin scope → authorization allowed;
- wrong evidence digest → finalizer returns
  `AUTHORIZATION_EVIDENCE_DIGEST_MISMATCH`;
- reused successful authorization → finalizer returns
  `AUTHORIZATION_REPLAYED`.

### Freshness

PASS:

Evidence older than 1,800 seconds was rejected with:

`EVIDENCE_TOO_OLD_FOR_EFFECTIVE_HEALTH`.

### Production authority exclusion

PASS:

A selected evidence run with a Production deployment carrying actual authority/effect
(`approved/deploying/deployed`, approver present, or deployed timestamp present)
was rejected with:

`SELECTED_EVIDENCE_RUN_HAS_PRODUCTION_AUTHORITY`.

### Positive path

PASS on synthetic DEV-only fixture:

- AAL2 human authorization produced an audit-bound authorization id;
- finalizer recomputed the evidence digest independently;
- finalization succeeded only with the matching digest/scope/run window;
- `vl_cert_health.updated_at` equalled the selected evidence timestamp, not wall-clock time;
- exactly one finalized audit was produced inside the test transaction;
- replay was rejected.

All fixture rows were rolled back. Residue checks after the test showed:

- synthetic auth users: 0
- synthetic project memberships: 0
- synthetic builders: 0
- synthetic factory runs: 0
- synthetic health rows: 0
- synthetic authorization audits: 0

## Reverse migration rehearsal

Reverse script:

`vl/ops/rollback_cert_health_activation_20261004.sql`

PASS.

After reverse + DEV-only tracking cleanup, the complete DEV fingerprint returned exactly to the Production baseline.

The reverse path was executed twice during rehearsal and produced full fingerprint recovery both times.

## Re-apply verification

Latest forward migration was applied again as DEV rehearsal v3:

- migration version: `20261004161031`
- name: `cert_health_activation_hardening_rehearsal_v3`

Final smoke:

- AAL1 authorization rejected;
- finalizer without current active-builder evidence returned HOLD;
- Security Advisor remained INFO-only;
- no synthetic runtime residue persisted.

## Production non-mutation verification

Final Production read-only check:

- `public.authorize_vl_cert_health_finalization(...)`: absent
- `private.finalize_vl_cert_health_from_fresh_certification(...)`: absent
- `public.get_vl_cert_health_effective(integer)`: absent
- `public.vl_reconcile_stale_factory_workflow(...)`: absent
- activation audit rows produced by this work: 0

Therefore repository/DEV validation did not deploy or activate Production.

## Remaining Production gates

1. independent human review of PR #475;
2. verified MFA/AAL2 enrollment for the authorized human operator;
3. current backup freshness evidence;
4. tested restore evidence for the Production database;
5. genuine fresh certification evidence for all active builders within the 30-minute effective-health window;
6. exact fresh evidence digest;
7. AAL2 human authorization bound to that digest/run window;
8. separate human approval for Production DDL;
9. post-deploy read-only verification;
10. separate human approval for certification-health finalization.

Principle: **Stabilize → Prove → Scale.**
