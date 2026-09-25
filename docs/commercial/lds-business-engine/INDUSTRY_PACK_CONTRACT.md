# LD Industry Pack Contract v1

Status: DEVELOPMENT / NON-PRODUCTION

## Rule 1 — Reuse before build

Before adding a capability, check the LD reusable catalog and existing owners. Extend the authoritative component when feasible. Do not create duplicate CRM, quotation, payment, accounting, QA, renderer, customer portal or deployment systems.

## Rule 2 — Single source of truth

Generic business state belongs to the LUNDUS Business Engine. Industry Packs add vocabulary, entities, validation and workflow extensions only.

## Rule 3 — Fail closed

Unsupported capabilities, unknown authority gates, incomplete configuration or ambiguous state must return HOLD rather than silently expanding authority.

## Rule 4 — Human authority

Final pricing exceptions, customer commitments, live charging, Production deployment, privilege widening and destructive Production actions remain human-gated.

## Rule 5 — Evidence

Pack activation must carry deterministic configuration evidence, version/digest, QA evidence and known limitations.

## Property / Broker Pack

Required vertical capabilities:
- LISTING
- MAP_VIEWER
- MATCHING
- VIEWING
- DEAL_PIPELINE

Primary entities:
- owner
- buyer
- broker
- property_listing
- lead
- viewing
- offer
- deal
- document

The pack reuses core CRM, quotation, payment, document, notification, approval and audit capabilities rather than replacing them.
