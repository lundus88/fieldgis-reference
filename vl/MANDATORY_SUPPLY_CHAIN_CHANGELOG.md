Mandatory supply-chain change set:
- Adds `VL Supply Chain Attestation` workflow.
- Adds OIDC-bound `vrs-supply-chain-oidc` authority.
- Adds DB migration requiring `supply_chain_attestation` for every builder profile.
- Adds DB trigger blocking ordinary callers from setting the gate PASS.
- Adds service-role-only RPC that verifies deployment/artifact SHA binding before recording PASS.
- Preserves explicit human production approval as a separate required control.
