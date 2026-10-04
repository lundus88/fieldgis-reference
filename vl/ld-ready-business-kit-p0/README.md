# LD Ready Business Kit P0

Status: COMPATIBILITY / REFERENCE / NON-PRODUCTION

## Goal

Preserve the original reusable business-site kit as a compatibility/reference implementation for legacy vertical presets and regression evidence. It is not the canonical LD website runtime.

Canonical runtime ownership now belongs to the existing **Professional Service Website Engine in LundusLead**, with the shared Design Library / Design DNA pipeline used for website composition.

Operating principle:

**Reuse canonical engine → map legacy preset/configuration → preview → QA → human gate**

The deterministic legacy renderer may remain for regression and migration checks, but it must not receive new customer-facing runtime features.

## P0 scope

- standardized onboarding schema
- vertical presets
- deterministic one-page HTML preview renderer
- WhatsApp CTA
- service/menu/room/course cards
- contact/maps/social placeholders
- basic lead-capture manifest
- deployment manifest
- fail-closed onboarding validation
- no payment activation
- no Production deployment

## Client flow

Lead → choose vertical → submit business details → validate → generate preview → client review → human approval → deploy

## Ownership

Client owns:
- domain
- business content
- business data

LD manages:
- template
- hosting/configuration where contracted
- updates
- QA
- automation modules

## P0 verticals

1. Cafe / F&B
2. Homestay
3. Tutor / Education

## Guardrails

- No public launch from P0.
- No live payment.
- No legal/tax/compliance claims.
- Final prices and discounts remain human-approved.
- Generated preview is not treated as customer acceptance.


## Flagship website template library

The flagship set is retained as governed preset/configuration metadata. New delivery must map these presets into the canonical Professional Service Website Engine rather than extending this legacy renderer.

Initial flagship set:
- Surveyor Pro
- Property & Land
- Contractor & Engineering
- SME Corporate
- Commerce Launch
- Premium Professional

Delivery lanes are bounded targets only: EXPRESS_24H, FAST_48H and STANDARD_3DAY. Eligibility requires ready customer inputs, locked scope and intact QA. Production release and customer commitments remain human-gated.

See `docs/commercial/LD_WEBSITE_TEMPLATE_LIBRARY_P0.md`.
