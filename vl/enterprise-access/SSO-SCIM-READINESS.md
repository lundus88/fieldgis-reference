# VL Enterprise Identity — SSO/SAML/SCIM Readiness

Status: architecture/contract only. No production identity provider is configured or claimed.

## Identity boundary

VL enterprise identity resolves a human principal into workspace and project membership. It does not grant execution authority by itself. Any agent/action capability remains subject to the Agent Control Plane (ACP), and the enterprise access layer may only narrow an existing ACP grant.

## Supported readiness targets

- OIDC SSO: issuer, client/audience, subject, workspace claim mapping, session provenance.
- SAML 2.0: entity ID, assertion audience, signed assertion requirement, immutable subject mapping, workspace/role mapping.
- SCIM 2.0: create/update/deactivate user, group-to-workspace mapping, idempotent external IDs, deprovisioning that disables membership rather than deleting audit history.

## Required invariants before live integration

1. Identity assertions must be cryptographically verified by the selected provider integration.
2. Unknown issuer/audience/subject fails closed.
3. Role claims are mapped through a versioned workspace policy; IdP claims cannot directly grant ACP capabilities.
4. Project membership remains explicit and exact-scope.
5. Deactivated SCIM users lose workspace/project access on the next authorization decision.
6. Session/device events record actor, workspace, authentication method, policy version and outcome without tokens or assertions.
7. `production.approve` is never inherited from SSO group membership alone; it requires a separate explicit human approval grant and separation-of-duties check.
8. Connector access requires the intersection of role eligibility, ACP capability, project connector scope and action-level approval policy.

## Public-sector mapping

Agency -> workspace
Department/division -> workspace group/policy inheritance
Programme/project -> VL project membership
Operational role -> owner/admin/builder/reviewer/auditor/viewer
Production approver -> separate explicit human approval grant, not a normal role entitlement

## Deployment status

`oidc_enterprise_sso = NOT_CONFIGURED`
`saml = NOT_CONFIGURED`
`scim = NOT_CONFIGURED`
`production_enforcement = NOT_ACTIVE`

A future provider-specific implementation requires its own integration tests and runtime evidence before any production-enforced claim.
