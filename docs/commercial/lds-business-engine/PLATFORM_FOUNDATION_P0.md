# LUNDUS Business Engine — Platform Foundation P0

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

Turn the reusable Business Engine into a scalable multi-client platform without introducing duplicate generic systems.

P0 adds four bounded control-plane capabilities:

1. Multi-tenant organisation identity.
2. Package / entitlement enforcement.
3. Industry Pack registry.
4. Capability Resolver with REUSE_BEFORE_BUILD policy.

## Multi-tenant boundary

A tenant is an organisation workspace identifier and configuration boundary.

P0 does not create or mutate a Production database. It defines a deterministic contract that future storage adapters must preserve.

A tenant cannot grant itself Production write authority.

## Entitlement boundary

Packages control which capabilities may be composed for a tenant.

A lower package fails closed when an Industry Pack requests capabilities outside its entitlement.

Pricing values are intentionally not embedded in this P0 engine. Commercial pricing remains separately human-controlled.

## Industry Pack Registry

The registry provides one deterministic inventory of Industry Packs. Duplicate pack identifiers fail closed.

The registry is configuration metadata, not an alternate renderer, CRM, payment engine, QA engine or deployment system.

## Capability Resolver

Before creating new generic capability code, LOM/VL must resolve the requested capability against an authoritative owner.

Known capability:
REUSE existing owner.

Unknown capability:
HOLD → REVIEW_BEFORE_BUILD.

This implements the architectural policy:

Need → Resolve → Reuse → Extend → Build only when absent and approved.

## Authority boundary

This P0 does not authorize:
- Production deployment;
- Production data mutation;
- live charging;
- privilege widening;
- customer commitment;
- automatic package upgrades.

Those remain separately human-gated.

## Organisation binding and RBAC

The Business Engine tenant contract is bound to the existing organisation model through `organization_ref`. This is deliberately an integration contract, not a second organisation database.

Runtime storage must preserve the authoritative organisation / membership controls already used by the platform.

P0 role permissions are least-privilege and bounded to non-Production actions:
- OWNER: view, operate, manage members, configure pack, request package change;
- ADMIN: view, operate, manage members;
- OPERATOR: view and operate;
- VIEWER: view only.

A matching role never grants Production deployment, live charging or other human-only authority.

Cross-tenant organisation mismatch fails closed.

## Capability dependency guard

Capability composition now validates required dependencies before ownership resolution. For example, PAYMENT cannot be composed without ORDER, and MATCHING cannot be composed without LISTING and LEAD_CRM.

This prevents a package or Industry Pack from producing a structurally incomplete runtime.

## Package change / downgrade guard

Package changes are never automatic in P0.

Any upgrade or downgrade returns a HUMAN_GATE. A downgrade reports capabilities that would leave entitlement but explicitly grants **no data deletion authority**. Existing customer data must not be destroyed merely because an entitlement changed.

## Post-merge hardening

The exact-main workflow must run after relevant merges to ensure the merged commit, not only the PR head, passes the Business Engine regression suite.

Tenant actions must be authorized from verified organisation-membership evidence. A caller-supplied role without membership evidence is not sufficient authority.

The Industry Pack Registry reuses the canonical Industry Pack validator. Registry admission also requires Production to remain LOCKED. This prevents a pack from bypassing capability, human-gate or Production-lock validation through the registry path.
