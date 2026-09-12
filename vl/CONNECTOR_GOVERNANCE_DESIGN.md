# LOM Connector Governance — Design Contract

Status: DESIGN-READY / IMPLEMENTATION-BLOCKED

This document records the intended Lundus Operating Model (LOM) connector-governance contract without enabling any live connector write, paid action, production mutation, credential change, or autonomous approval.

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
9. Connector decisions must emit request, grant and decision digests without secret values.
10. Any missing policy, unknown connector, out-of-scope resource or uncertified runtime fails closed.

## LOM v1 implementation boundary

Initial implementation target is read-only, non-production connector governance only.

Permitted candidate class:

`connector.read:<connector-id>`

Explicitly excluded from LOM v1 connector runtime activation:

- connector writes
- purchases or paid operations
- account creation or resource provisioning
- destructive operations
- production data mutation
- secret/key administration
- production approval or deployment

## Acceptance criteria

A future implementation is acceptable only when tests prove:

- uncertified connector => DENY
- missing grant => DENY
- resource scope escape => DENY
- non-read operation in v1 => DENY
- ambient credential dependency => DENY
- missing/unknown policy => DENY
- read-only in-scope request with valid grant => ALLOW
- decision evidence is deterministic and contains no secret material
- `production_locked=true`
- write authority remains false

## Runtime evidence rule

Contract and CI evidence do not constitute live connector runtime proof. Runtime status must remain `NOT_DEPLOYED` until an actual non-production connector path is exercised with machine-readable evidence.

## Sequencing

Connector Governance must be proven before LOM allows controlled multi-agent workers to invoke external systems. Execution Pool and Multi-Agent modules may be designed in parallel, but connector authority cannot be inferred or inherited from them.
