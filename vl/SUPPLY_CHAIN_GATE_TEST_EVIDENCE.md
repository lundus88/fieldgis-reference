# Supply-Chain Gate Test Evidence

Branch test workflow: `VL Supply Chain Attestation`
Run ID: `33244412177`
Result: PASS

Verified steps:
- Resolve a successful `VL Factory Runner` run that emitted an immutable `vl-factory-*` artifact.
- Download the exact GitHub Actions artifact.
- Generate SPDX 2.3 SBOM bound to artifact SHA-256.
- Generate GitHub signed provenance attestation.
- Generate GitHub signed SPDX SBOM attestation.
- Verify provenance with `gh attestation verify`.
- Verify SPDX attestation with `gh attestation verify --predicate-type https://spdx.dev/Document/v2.3`.
- Verify artifact SHA-256 equals the checksum declared by the signed SBOM.
- Upload evidence bundle.

The production DB callback was intentionally skipped during branch testing. Production promotion, rollback, payment and customer-data mutation were not performed.
