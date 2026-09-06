# VL Historical Factory Orphan — Governed Disposition

Status: observability/reconciliation contract only. No factory/workflow state mutation is authorized by this document.

## Classification outcomes

- `NO_ACTION` — observed run does not match the stale validating + runner PASS + no deployment pattern.
- `HISTORICAL_ORPHAN_CANDIDATE` — stale historical run matches the known residue pattern and was created before the current default-environment provisioning path.
- `CURRENT_PATH_REGRESSION_REQUIRES_REVIEW` — the same stale pattern appears on the current provisioning path; this is not treated as historical cleanup and requires engineering review before stronger preflight changes.
- `REVIEW_REQUIRED` — observability fields are missing or insufficient.

## Disposition rules

1. The detector is read-only and must never update `factory_runs`, `workflows`, `deployments`, release gates, certification rows or production approvals.
2. A historical candidate must not be relabeled PASS, certified, deployed or promoted merely because the runner reported PASS.
3. Reconciliation requires an explicit governed operation whose authority is narrower than production promotion and whose inputs bind to the immutable factory-run/artifact provenance.
4. Until such a reconciliation operation is implemented and independently reviewed, the recommended disposition is `REVIEW_AND_RECONCILE`.
5. A current-path recurrence is evidence of a regression and must not be auto-cleaned as historical residue.
6. The stale threshold is an explicit observability parameter supplied by the caller; it is not a hidden production SLA or release rule.
7. Machine-readable blocked observations may be emitted with digests and reason codes, but they must not mutate the run state.

## Known historical case

Factory run `cd2ae968-ccd4-4222-b140-ed463dc72fbb` remains a historical orphan candidate based on read-only evidence as of 2026-09-06:
- factory state `validating`;
- workflow state `running`;
- runner status/QA `PASS`;
- deployment count `0`;
- immutable artifact provenance exists;
- no direct cleanup is performed.

## Production boundary

`direct_state_mutation = FORBIDDEN`
`automatic_certification = FORBIDDEN`
`automatic_production_approval = FORBIDDEN`
`recommended_disposition = REVIEW_AND_RECONCILE`
