Rollout order:
1. Merge this PR through `VL Main Protection` after `governance-policy` passes.
2. Deploy `vrs-supply-chain-oidc` from the merged source with `verify_jwt=false`; the function performs strict GitHub OIDC verification itself.
3. Apply `20260829_mandatory_supply_chain_attestation.sql` using the governed Supabase migration action.
4. Verify every builder profile contains `supply_chain_attestation` and policy version/hash changed.
5. Verify an unauthorized direct update of the gate to PASS is rejected.
6. Run `VL Supply Chain Attestation` against a real immutable Factory Runner artifact and require OIDC callback PASS.
7. Verify the corresponding release gate is PASS with matching artifact SHA, signed provenance, signed SPDX SBOM and build/attestation run IDs.
8. Confirm human production approval remains a separate pending gate.
