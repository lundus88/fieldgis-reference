# VL Mandatory Supply-Chain Attestation Gate

This control makes cryptographic artifact provenance and an SPDX 2.3 SBOM mandatory before technical release certification may complete.

Enforcement model:
- `VL Supply Chain Attestation` processes the immutable artifact emitted by `VL Factory Runner`.
- The artifact is signed with GitHub artifact attestation and receives a signed SPDX 2.3 SBOM attestation.
- Both attestations are verified with `gh attestation verify` against `lundus88/fieldgis-reference`.
- The artifact SHA-256 is bound to the deployment SHA-256 in the control-plane database.
- Only the OIDC-bound `vrs-supply-chain-oidc` authority may set `supply_chain_attestation` to PASS.
- A database trigger rejects attempts by the ordinary release validator or other callers to set this gate PASS.
- Every builder release-gate profile includes `supply_chain_attestation`; missing evidence therefore fails closed and prevents certification/production approval.

This gate does not approve or promote a production release. Explicit human production approval remains mandatory and separate.
