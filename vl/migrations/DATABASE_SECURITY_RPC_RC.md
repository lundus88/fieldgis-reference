# Issue #211 — database security RPC release candidate

Status: repository remediation prepared; **PRODUCTION HOLD**.

**PRODUCTION NOT MODIFIED** by this work. A concurrent, separately merged change is described below.

**HUMAN PRODUCTION APPROVAL STILL REQUIRED**

## Incident and verified starting point

- Authoritative repository: `lundus88/fieldgis-reference`.
- Branch: `vl/p0-database-security-gate-remediation`.
- Starting branch/main HEAD: `ae0ced38dce48b03e4dcba0f54feea79a059fc87`.
- Fresh clone was clean. Issue [#211](https://github.com/lundus88/fieldgis-reference/issues/211) was read completely; it had no comments.
- Factory run: `25415bd6-568c-48c0-821b-45fada93a810`, builder `web-react-v1`.
- Factory runner [34816892291](https://github.com/lundus88/fieldgis-reference/actions/runs/34816892291): incident records PASS.
- Release validator [34817173078](https://github.com/lundus88/fieldgis-reference/actions/runs/34817173078): workflow success, backend `technical_gates_failed`.
- Production catalog read on 2026-09-14 confirmed `public_tables_without_rls=0` and `public_security_definer_exposed_to_client_roles=3`.
- All three affected public RPCs were DEFINER, authenticated-executable and anon-denied. The private alignment generator was DEFINER/client-denied; its validator was INVOKER/anon-executable.
- A read-only Data API request with `Accept-Profile: private` returned HTTP 406 / `PGRST106`: only `public, graphql_public` are exposed. The catalog GUC was null, so it was **not** used as proof of non-exposure.

No migration, production RPC mutation, release-validator dispatch, approval, promotion, schema change, or deployment was performed against `vrs-core`.

### Concurrent main update reconciled

After the initial RC was pushed, final verification found main had advanced to `98f766f1529534f779f2ea5c2033945280ec8b57`, including [PR #216](https://github.com/lundus88/fieldgis-reference/pull/216). Its additive `20260914_public_security_definer_boundary.sql` already changes the three public RPCs to INVOKER, but grants authenticated EXECUTE on three private SECURITY DEFINER implementations. A subsequent **read-only** production check confirmed public counts `0 / 0` and all three of those private helper grants active. Therefore the original public exposure is no longer claimed to remain live.

This RC incorporates that main history without rewriting it and completes the directive's stricter private-helper-denial requirement. The migration is named **`20260914_security_invoker_rpc_guarded_entry.sql`**, intentionally sorting after the newly merged migration instead of using the original suggested filename. It preserves PR #216's file/helper bodies, revokes client execution of its three legacy helpers, locks their search paths and installs the guarded public entry paths atomically. No scheduler/watchdog or release-validator change from main is altered by this RC.

## Architecture and strict helper-execution boundary

The public signatures, argument names, defaults and JSONB returns remain:

| Public RPC | Execution after migration | Privileged operation |
| --- | --- | --- |
| `request_vrs_internal_usage_override(uuid,text,integer)` | INVOKER | INSERT into a private, empty request view; its INSTEAD OF INSERT trigger performs the original guarded override/audit writes |
| `vl_get_assisted_build_quote(text)` | STABLE INVOKER | SELECT from a private security-barrier view projecting only the existing quote JSON for enabled policies and a non-null authenticated identity |
| `vl_prepare_assisted_build_product_alignment(jsonb,jsonb)` | STABLE INVOKER | Calls the existing private generator and validator, both now nonprivileged INVOKER functions |

An ordinary INVOKER facade cannot call a helper when the calling role lacks EXECUTE. Granting authenticated EXECUTE on a privileged helper would contradict the directive's stricter helper-denial requirement. The override therefore uses PostgreSQL's guarded trigger path: clients get only INSERT on the three input columns and SELECT on the returned result column of an empty view. They cannot execute or attach the privileged trigger helper, read stored overrides/audits, provide a result, update an override or bypass checks through a direct INSERT. The view stores no requests or results.

The private quote view intentionally uses its owner's narrow policy-read authority. It returns the existing quote payload only, with an identity filter, enabled-policy filter and security barrier. It grants no raw policy-table access and no writes. This is the read-only alternative to making a privileged lookup helper client-executable. Both views must remain outside Data API exposed schemas.

The alignment helpers only transform input JSON. Their authenticated EXECUTE grants do not confer elevated database authority. Backend `service_role` EXECUTE on these **nonprivileged** helpers preserves backend compatibility when PUBLIC EXECUTE is revoked; it is not used in any client path. Native `pg_catalog.sha256` replaces `pgcrypto.digest(...,'sha256')`, removing extension search-path/privilege dependencies. Both hashes and the entire JSON result match the historical function in the PostgreSQL fixture.

All affected function search paths are empty with schema-qualified relation/helper references. PUBLIC and anon cannot execute the public RPCs. PUBLIC, anon, authenticated and service_role cannot execute the privileged trigger helper. PUBLIC, anon and authenticated also lose execution on PR #216's three legacy privileged helpers; their backend permissions are retained. The additive migration uses a transaction, replay-safe CREATE OR REPLACE, explicit table/column ACL reset for the new views and fail-closed postcondition assertions, including unexpected inherited access to raw private tables and legacy helper grants.

## Controls retained

- Authenticated identity, AAL2 MFA, owner/admin membership scoped to the requested project.
- Trimmed reason of at least 12 characters; duration 1..240 minutes, default 60. Explicit null duration now fails with the bounded-duration error before any write.
- Existing override constraints, expiry/revocation data, and transactional audit insert. An audit failure rolls back the override.
- Approval/promotion change/bypass flags remain false.
- Quote and alignment preparation remain read-only; no payment, factory run, approval or promotion action.
- Historical migrations, Assisted Build UI, release scanner/evaluator, release validator, production approval endpoint, production promoter, production locks and existing CI checks are unchanged.

## Executed repository validation

| Validation | Result |
| --- | --- |
| Pre-change Assisted Build, Governance CI, migration reproducibility/schema-capture steps plus founder guardrail | 10/10 command steps passed |
| `python3 vl/tests/check_database_security_rpc.py` | 10 passed, 0 failed |
| `npm ci --ignore-scripts && npm test` in `vl/tests/database-security` | Node reports 56 passed, 0 failed (55 subtests plus parent) |
| Post-change Assisted Build workflow, including new database-security job, Governance CI and migration reproducibility workflow equivalents | 12/12 command steps passed |
| Broader `python3 vl/scripts/check_action_pinning.py` | FAIL: 25 pre-existing mutable action references across the repository |

The action-pinning checker was also executed against the exact starting commit's workflow files: 86 workflows and 25 findings. Before the concurrent main integration its complete output was identical. The updated main adds a pinned watchdog workflow; the final audit scans 87 workflows and retains the same 25 findings. The changed Assisted Build workflow retains SHA-pinned actions and adds no finding. This pre-existing failure is disclosed, not suppressed or declared PASS.

The fixture runs **PostgreSQL 17.5** through pinned PGlite `0.4.6`; production reports PostgreSQL `17.6.1.155`. It loads the actual historical RPCs, relevant table definitions/constraints and real pgcrypto extension, then PR #216's exact migration and this successor migration/replay. The new dependency is test-only, integrity-locked and installed with lifecycle scripts disabled. Local execution used Node 24; GitHub CI is configured for Node 22.

Tests cover catalog privileges, real anon/authenticated calls, missing identity, AAL1/missing AAL, other-project/nonmember/member rejection, short/null reasons, duration boundaries/null, successful owner/admin/default-duration requests, direct private entry attempts, helper attachment denial, atomic audit failure, disabled/missing policies, exact historical quote/alignment JSON and hashes, read-only transactions, temporary-object shadowing and ACL repair on replay.

| Scope | Tables without RLS | Exposed public DEFINER RPCs | Meaning |
| --- | ---: | ---: | --- |
| Production catalog, initial read-only baseline | 0 | 3 | Original incident confirmed |
| Production catalog, later read-only check after concurrent PR #216 | 0 | 0 | Three affected private DEFINER helpers still authenticated-executable; no production writes by this work |
| Repository fixture before migration | 0 | 3 | Reproduced the relevant boundary failure |
| Repository fixture after PR #216 | 0 | 0 | Three client-executable private DEFINER helpers |
| Repository fixture after successor/replay | 0 | 0 | Zero client-executable private DEFINER helpers; public scanner predicates unchanged |
| Complete Supabase DEV control plane | Not tested | Not tested | `BLOCKED_DEV_DATABASE_VALIDATION` |

These are test results, not certification/release-gate records. No PASS was written to a release database. The repository lacks a complete replayable production schema baseline; the fixture supplies explicitly limited test scaffolding and does not claim full migration reproducibility. Full mobile/device/platform CI, live Assisted Build browser flows and the Controlled Canary were not run by this work. Applicable PR checks are reported by GitHub on the PR revision.

## Development validation blocker and next operator action

Supabase discovery returned only the default production branch for `vrs-core`. No safe VL DEV database was available. The inactive QuoteFlow staging project and other products' projects are not substitutes. No new paid branch was provisioned.

**Next action:** provide a separate, authorised VL Supabase DEV branch/database with verified schema provenance. Keep this PR unmerged and production on HOLD while these checks remain outstanding:

1. Verify the DEV project ref differs from `wczelfmnqpgzfdszxubl`, establish the canonical schema/dependencies, and confirm `private` is not exposed by the Data API.
2. Apply the additive migration to DEV only, record its checksum and run `vl/tests/database-security/privilege-evidence.sql`. Require public RPC INVOKER flags, authenticated access, anon/PUBLIC denial, private privileged helper denial and scanner counts `0 / 0`.
3. With dedicated DEV test identities, exercise PostgREST named RPC calls and the actual Assisted Build review/save flow; test AAL1/AAL2 and owner/admin/nonmember cases. Verify stored audit/expiry records and raw-table denial.
4. Run the Controlled Canary on DEV and record real database_security evidence and unchanged human production-approval/promotion boundaries. Resolve the separate action-pinning findings through normal review.
5. Review the exact PR HEAD and CI. Merge/deploy/promotion require a later explicit human instruction; this RC provides none of those approvals.

## Rollback

Before rollout, close/revert this development PR if needed; no live rollback is necessary. On DEV, discard the isolated test branch or forward-fix the migration. Never delete existing override/audit records or restore client-executable public SECURITY DEFINER RPCs as an availability shortcut.

If a later separately authorised rollout needs emergency containment, keep production/release HOLD and have the authorised operator disable the affected public RPCs while preparing a reviewed forward fix:

```sql
begin;
revoke execute on function public.request_vrs_internal_usage_override(uuid,text,integer) from public, anon, authenticated;
revoke execute on function public.vl_get_assisted_build_quote(text) from public, anon, authenticated;
revoke execute on function public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb) from public, anon, authenticated;
commit;
```

This containment temporarily disables those client features. It preserves the private helper denial, stored audits and all production locks. These instructions are for operator review and have not been executed.

## Technical references

- [PostgreSQL function execution privileges](https://www.postgresql.org/docs/17/sql-createfunction.html)
- [PostgreSQL view permissions and security barriers](https://www.postgresql.org/docs/17/sql-createview.html)
- [PostgreSQL trigger creation privileges](https://www.postgresql.org/docs/17/sql-createtrigger.html)
- [PostgreSQL native SHA-256](https://www.postgresql.org/docs/17/functions-binarystring.html)
- [Supabase database functions](https://supabase.com/docs/guides/database/functions)

The Supabase changelog was checked for relevant changes. The solution keeps explicit grants and the existing exposed-schema boundary and does not depend on automatic Data API exposure.
