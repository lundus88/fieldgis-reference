# VL Agent Control Plane V1

Status: Repository contracts merged; narrow live write boundary under review for Issue #95. No ACP production migration or edge deployment has occurred.

## Purpose

The Agent Control Plane (ACP) governs every autonomous or delegated agent action that can affect VL state or invoke an external connector. It is a fail-closed layer between agent intent and execution.

## Core invariants

1. No ambient authority. Every action must name one capability and one bounded resource scope.
2. Default deny. Unknown capabilities, missing scope/provenance, expired actions, invalid delegation, or unavailable policy evidence are denied.
3. Agents cannot widen their own authority. A delegated capability set must be a subset of the delegator's effective capabilities.
4. Production approval remains human-only. `production.approve` is never autonomously granted in V1.
5. Generated/untrusted code never receives ACP credentials or connector credentials.
6. Externally effective actions require deterministic idempotency/replay protection.
7. Every request, decision, execution result and delegation edge emits immutable audit evidence without secret values.
8. Persisted grants are authoritative only after successful grant-chain resolution; unresolved, revoked, expired, cyclic or widened delegation fails closed.

## Action lifecycle

Agent request -> validate envelope -> load authoritative persisted grant -> resolve delegation chain -> validate effective capabilities/scope/budget/expiry -> evaluate policy -> ALLOW / DENY / REQUIRE_HUMAN_APPROVAL -> execute bounded action -> record immutable result.

Execution MUST NOT begin before a machine-readable policy decision exists.

## Agent identity

Required fields:
- `agent_id`
- `agent_version`
- `role`
- `principal_type` (`agent`, `human`, `system`)
- optional `delegated_by`

Identity is descriptive, not authoritative by itself. Effective authority comes from policy-bound capabilities and scope.

## Capability model

Initial V1 capability vocabulary:
- `spec.read`
- `spec.propose`
- `factory.plan`
- `factory.enqueue`
- `artifact.read`
- `qa.execute`
- `certification.propose`
- `release.request_approval`
- `connector.invoke:<connector>`

Reserved/high-risk capabilities:
- `production.approve` — human only
- `production.promote` — requires existing approved immutable release evidence and policy gate
- secret/key administration — excluded from worker agents
- ACP policy mutation — excluded from worker agents

## Resource scope

Every action must bind to the minimum needed scope. Supported scope keys include:
- `project_id`
- `factory_run_id`
- `artifact_id`
- `connector`
- `target_environment`

A policy may require multiple scope keys. Scope values are exact-match unless an explicitly versioned policy defines otherwise.

## Delegation

Delegation is monotonic-restrictive:

`child_effective_capabilities ⊆ parent_effective_capabilities`

A child grant cannot escape the parent's project/resource scope, extend expiry, increase retry/spend/time budgets, or introduce a new connector. Any violation is `DENY`.

The runtime grant resolver must also reject:
- missing parent grant evidence;
- revoked grants anywhere in the chain;
- expired grants anywhere in the chain;
- delegation cycles;
- delegation depth beyond the configured bound;
- agent identity mismatch for the leaf grant.

Grant resolution is storage-agnostic in code, but the authoritative persistence contract is `private.agent_capability_grants`. Runtime callers must load persisted grant rows from that private store before policy evaluation. The resolver itself never reads ambient credentials.

## Decision outcomes

- `allow`
- `deny`
- `require_human_approval`

Stable reason codes include:
- `ALLOW_POLICY_MATCH`
- `DENY_UNKNOWN_CAPABILITY`
- `DENY_CAPABILITY_NOT_GRANTED`
- `DENY_SCOPE_MISMATCH`
- `DENY_DELEGATION_ESCALATION`
- `DENY_EXPIRED_ACTION`
- `DENY_REPLAY`
- `DENY_MISSING_PROVENANCE`
- `DENY_POLICY_UNAVAILABLE`
- `REQUIRE_HUMAN_PRODUCTION_APPROVAL`

## Replay and idempotency

Externally effective actions require a deterministic `action_id` and idempotency record. Reusing an already-consumed `action_id` with different canonical inputs is denied. Repeating an identical action may return the recorded result without re-execution.

## Budgets

An action may carry bounded budgets:
- `timeout_seconds`
- `max_retries`
- optional `max_cost_minor`

Delegation can only keep or reduce budgets.

## Audit evidence

Audit events must record:
- action ID
- requester identity
- delegator chain identifiers
- capability
- resource scope
- canonical input digest
- policy decision and reason code
- execution result/status
- timestamps

Audit persistence is append-only/tamper-evident by contract. UPDATE, DELETE and TRUNCATE are rejected at the datastore boundary. Never record bearer tokens, service-role keys, API secrets, raw connector credentials or other secret material.

## Narrow live write boundary

The first live-write candidate is deliberately smaller than the full ACP runtime surface.

Allowed operations:
- delegate an **agent** grant from an existing parent grant;
- revoke an existing **agent** grant.

Hard boundaries:
- no runtime root-grant creation;
- no `production.approve` or `production.promote` delegation;
- delegated target environment must be `development` or `staging`;
- database triggers independently enforce parent capability/scope/budget/validity restrictions;
- `service_role` has no direct DML on the ACP private tables;
- only two service-role-executable `SECURITY DEFINER` RPCs exist for this rollout;
- state mutation and its immutable audit evidence are committed atomically;
- no generic public/service-role audit writer exists;
- the OIDC edge candidate is bound to one exact repository, branch, audience and dedicated admin workflow reference;
- authentication failures are separated from request, policy/database, and internal failures.

The dedicated admin workflow is intentionally not part of the initial boundary PR. Without that separately reviewed workflow, the OIDC boundary remains fail-closed even if deployed accidentally.

## Integration with existing VL lifecycle

ACP does not replace existing factory governance. It wraps agent-driven transitions into:

Natural-language intake -> App Spec -> builder routing -> staging factory run -> CI/build -> artifact -> QA -> certification -> human production approval -> immutable promotion -> rollback/audit.

The human production approval gate remains authoritative and unchanged.

## V1 adversarial acceptance

The implementation must prove fail-closed behavior for:
1. unknown capability;
2. ungranted capability;
3. project/resource scope escape;
4. forged or widened delegation;
5. expired action/grant;
6. replay with changed inputs;
7. missing provenance or missing grant-chain evidence;
8. revoked grant;
9. delegation cycle/depth escape;
10. attempt by an agent to approve production.

Repository implementation now includes contract schemas, runtime evaluator, grant-chain resolver, hardened persistence contract, guarded non-production transition boundary, narrow live-write candidate, OIDC boundary candidate, and regression suites. It is still **not** a production ACP deployment: the ACP migrations are not applied, the edge function is not deployed, no root/parent grant is bootstrapped, and no live ACP admin workflow exists.

No multi-agent swarm should be considered production-ready until end-to-end enforcement has machine-readable evidence.
