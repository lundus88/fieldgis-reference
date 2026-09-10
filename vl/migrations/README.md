Apply repository migrations through the governed Supabase migration path only. `20260829_mandatory_supply_chain_attestation.sql` must be applied together with deployment of `vrs-supply-chain-oidc` after the corresponding GitHub workflow is merged to `main`, so the control plane fails closed without creating an unserviceable gate window.

## Reproducibility

Migration reproducibility is a P0 control-plane requirement. See `MIGRATION_REPRODUCIBILITY_RECOVERY.md` and `reproducibility_manifest.json`.

- Do not edit historical production-used migrations merely to make a fresh branch pass.
- Do not create synthetic certification PASS evidence, approvals, deployments, or refreshed health timestamps for replay.
- Recover schema history through a canonical linked schema pull, explicit schema-parity review, migration-history comparison, and tracking-only repair when parity is proven.
- A fresh data-less DEV environment must eventually build without manual DDL scaffolding before migration reproducibility can be marked GREEN.
