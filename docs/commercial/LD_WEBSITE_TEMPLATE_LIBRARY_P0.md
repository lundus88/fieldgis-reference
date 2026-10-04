# LD Website Template Library + Design System P0

Status: COMPATIBILITY / REFERENCE / NON-PRODUCTION

## Objective

Preserve the flagship website presets and design metadata as a compatibility/reference layer while reusing the canonical website runtime. This layer must not evolve into a second renderer, CRM, payment system, quotation engine, transaction store or deployment engine.

Canonical architecture:

Customer intent
→ choose industry / outcome
→ flagship preset / configuration
→ canonical Professional Service Website Engine in LundusLead
→ Design Library / Design DNA
→ lead capture / LundusLead
→ Golden Transaction for quotation/sale authority
→ existing QA / preview
→ human approval
→ controlled Production release

The legacy LD Ready Business Kit renderer remains available only for regression, migration and reference compatibility. No new customer-facing runtime capability should be added to it.

## Six flagship templates

1. **Surveyor Pro** — surveying & geospatial services; technical-premium; target lane FAST_48H.
2. **Property & Land** — broker / property; editorial-luxury; target lane FAST_48H.
3. **Contractor & Engineering** — project evidence + quotation path; industrial-clean; target lane FAST_48H.
4. **SME Corporate** — small/growing business; modern-clean; target lane EXPRESS_24H.
5. **Commerce Launch** — product catalogue / purchase intent; conversion-bold; target lane STANDARD_3DAY.
6. **Premium Professional** — consultants / professional services; minimal-premium; target lane EXPRESS_24H.

These are bounded delivery targets for eligible work, not unconditional promises.

## Design-system contract

Every flagship template must include:
- Hero with one primary proposition.
- Trust/proof section.
- Offer/service/product section.
- Clear process.
- Primary CTA.
- Mobile-first responsive intent.
- WhatsApp CTA + structured lead capture.
- Basic analytics and SEO metadata capability.
- Accessible hierarchy, readable typography and controlled visual density.

Optional blocks:
- portfolio / case studies;
- testimonials;
- FAQ;
- map;
- product catalogue;
- payment adapter;
- quotation workflow.

## Conversion-first rule

A template is not accepted merely because it looks attractive.

Each template declares one primary conversion goal such as:
- qualified enquiry;
- property lead;
- quotation request;
- business enquiry;
- purchase intent;
- consultation enquiry.

The template must expose the conversion path in the page structure.

## Delivery lanes

### EXPRESS_24H
Eligible only when:
- customer inputs are complete;
- scope is locked;
- the selected template fits without structural redesign;
- no custom integration is required;
- QA remains intact.

### FAST_48H
For bounded multi-section sites that require moderate content adaptation, portfolio/data population or quotation-oriented composition.

### STANDARD_3DAY
For commerce-oriented work or sites that require additional configuration and adapter checks.

Customer delay, missing content or scope change pauses/rebaselines the clock.

## Ownership and portability

The existing LD ownership boundary remains authoritative:
- client owns domain, business content and business data;
- LD manages template/configuration, hosting where contracted, QA and automation modules.

The template library must not create artificial data or domain lock-in.

## Anti-duplication

The library is configuration + design metadata only.

Canonical ownership:
- **Professional Service Website Engine (LundusLead)** = website runtime/rendering authority;
- **LD Design Library / Design DNA** = reusable design variation authority;
- **LundusLead** = lead/CRM/marketing system of record;
- **Golden Transaction** = quotation/sale control authority;
- **LUNDUS Business Engine** = orchestration/policy composer only, not a second transaction store;
- **LD Ready Business Kit P0** = compatibility/reference renderer only;
- existing payment, accounting, booking, WhatsApp, analytics, QA and deployment boundaries remain adapters or governed shared capabilities.

The six flagship templates are presets/configuration inputs to the canonical website engine. They must not become independent runtimes.

Build-new is allowed only after a proven capability gap and an explicit ownership review confirms that no existing authority can satisfy the requirement.

## Measurement

Template performance should eventually be measured by:
- time to first preview;
- QA pass rate;
- customer acceptance;
- time to first qualified enquiry;
- conversion rate;
- revision count;
- delivery variance;
- support incidents.

A visually attractive template with poor business outcome should not remain a flagship by default.

## Authority

P0 grants no:
- Production deployment authority;
- live charging authority;
- final-pricing authority;
- customer commitment authority.

Those remain HUMAN_ONLY.
