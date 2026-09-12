# LOM Connector Governance — Design Contract

Status: STATIC CONTRACT IMPLEMENTED / LIVE RUNTIME NOT DEPLOYED

This document records the Lundus Operating Model (LOM) connector-governance contract without enabling any live connector write, paid action, production mutation, credential change, or autonomous approval.

## Purpose

LOM must treat every external connector as an explicitly governed capability. No agent receives ambient connector authority.

## Required invariants

1. Every connector has an identity, version and certification status.
2. Connector access is deny-by-default.
3. Every request is bound to an explicit operation and resource scope.
4. Secrets and connector credentials are never exposed to worker agents or generated code.
5. Read-only operations must be explicitly granted and remain within declared resource scope.
6. Write, paid, provisioning, destructive and production-impacting operations remain blocked until a separately reviewed human-approval runtime exists.
7. A boolean supplied by the caller is not acceptable proof of human approval.
8. Approval evidence, when implemented later, must be independently issued, attributable to a human principal, bound to the exact canonical request digest, and auditable.
9. Connector decisions must emit request, grant and decision digests without secret values when a live runtime is later introduced.
10. Any missing policy, unknown connector, out-of-scope resource or uncertified runtime fails closed.

## LOM v1 implementation boundary

The current implementation is a declarative, read-only, non-production connector registry plus a static validator:

- `vl/connector-governance/connector-registry.json`
- `vl/connector-governance/validate_connector_registry.py`

The registry is deny-by-default and asserts:

- `production_locked=true`
- `write_authority=false`
- `paid_action_authority=false`
- `ambient_credentials_allowed=false`
- allowed operation is read only
- fixture connector has `external_runtime=false`
- fixture connector requires no credentials

No live external connector is invoked by this implementation.

Explicitly excluded from LOM v1 connector runtime activation:

- connector writes
- purchases or paid operations
- account creation or resource provisioning
- destructive operations
- production data mutation
- secret/key administration
- production approval or deployment

## Acceptance criteria

The current static implementation is acceptable when CI proves:

- registry is deny-by-default
- connector entries are uniquely identified and versioned
- only read operations are declared
- explicit resource scopes exist
- no ambient credentials are permitted
- no external runtime is enabled
- `production_locked=true`
- write authority remains false

A future live connector runtime must additionally prove request/grant/resource authorization, deterministic decision evidence, and no secret material exposure.

## Runtime evidence rule

Static contract and CI evidence do not constitute live connector runtime proof. Runtime status remains `NOT_DEPLOYED` until an actual non-production connector path is exercised with machine-readable evidence.
