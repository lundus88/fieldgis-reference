# LOM Execution Pool — Design Contract

Status: DESIGN-READY / NOT RUNTIME-ACTIVE

This document defines the Lundus Operating Model (LOM) execution-pool contract without enabling production credentials, production deployment, connector writes, or autonomous promotion.

## Purpose

LOM must execute generated or agent-produced work only inside a known, certified, bounded execution environment. The execution pool is an isolation and evidence layer, not an authority source.

## Required pool identity

Every pool must declare and attest:

- pool identifier
- profile version
- immutable image digest
- network policy
- CPU ceiling
- memory ceiling
- allowed capabilities
- certification status
- explicit absence of ambient production credentials

Unknown, incomplete or uncertified pools fail closed.

## Core invariants

1. No ambient production credentials.
2. Pool capability is explicit and bounded.
3. Requested CPU/memory may not exceed pool ceilings.
4. Requested network policy must match the certified profile.
5. Pool execution does not grant connector authority.
6. Pool execution does not grant production approval or deployment authority.
7. Artifacts must be bound to exact pool/profile/image evidence.
8. Execution evidence must remain attributable and machine-readable.
9. A worker cannot widen its capability by selecting a different pool.
10. Production remains locked even when a non-production artifact passes execution checks.

## LOM v1 runtime boundary

Initial runtime target is development/staging only.

Explicitly excluded:

- production credentials
- production database mutation
- production deployment
- secret administration
- connector write authority
- production approval
- autonomous artifact promotion

## Required decision evidence

A pool decision must record at minimum:

- pool id
- profile version
- image digest
- requested capability
- CPU/memory request
- network policy
- decision and reason code
- canonical request digest
- pool-policy digest
- `production_locked=true`

## Artifact attestation

Artifacts produced by a certified non-production pool should record:

- artifact SHA-256
- pool id
- profile version
- image digest
- network policy
- source/App Spec linkage when available

Attestation proves where an artifact was produced. It does not itself constitute release certification or production approval.

## Acceptance criteria

A future implementation must prove:

- incomplete identity => DENY
- uncertified pool => DENY
- ambient production credentials => DENY
- capability outside pool profile => DENY
- CPU ceiling exceeded => DENY
- memory ceiling exceeded => DENY
- network mismatch => DENY
- certified bounded development/staging request => ALLOW
- artifact attestation binds to exact immutable pool/image evidence
- `production_locked=true` always remains true

## Sequencing

Execution Pool design may proceed while Connector Governance is implementation-blocked because execution authority and connector authority are separate. Controlled Multi-Agent runtime must not become active until both execution and connector boundaries are independently proven.
