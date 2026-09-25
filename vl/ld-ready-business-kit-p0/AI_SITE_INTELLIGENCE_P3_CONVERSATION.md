# LD AI Site Intelligence P3 — Conversational Editing to SiteSpec Patch

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

Allow a customer to request safe website revisions in natural language while preserving one renderer, one SiteSpec contract, one QA path and explicit human authority.

Flow:

**Current SiteSpec + Current Onboarding + User Edit Request → bounded edit actions → optimistic-concurrency check → revised SiteSpec/onboarding → Existing Renderer → Preview → QA**

Examples of intended requests:

- “Besarkan tajuk.”
- “Jadikan gaya lebih premium.”
- “Tukar CTA kepada Tempah melalui WhatsApp.”
- “Susun Set Lunch di depan.”

## Architecture

P3 does not let free-form conversation mutate HTML, CSS, JavaScript, business identity, payment configuration or Production state.

The conversation text is retained only as a digest for evidence. A model/UI may propose actions, but the mutation engine accepts only an allowlisted edit language.

Supported P3 operations:

- SET_HEADLINE
- SET_CTA_LABEL
- SET_TONE
- SET_STYLE_HINTS
- SET_LAYOUT_DENSITY
- SET_HEADLINE_SCALE
- REORDER_CARDS

Business name, vertical, WhatsApp number and authority fields are not editable through this path.

## Concurrency and evidence

P3 introduces ld.ai-site-edit-state/1.

Every editable state contains:

- revision number;
- SiteSpec;
- onboarding data;
- deterministic state digest.

Every edit must bind to the exact base state digest. A stale or tampered state fails closed.

Accepted edits produce:

- incremented revision;
- new state digest;
- edit-request digest;
- normalized-actions digest;
- explicit changed-fields evidence.

This prevents a later edit from silently applying to an older website state.

## Renderer reuse

P3 extends the existing Ready Business Kit renderer with bounded design tokens rather than creating a second renderer.

Renderer-supported tokens in this phase:

- layout density: dense / balanced / sparse;
- headline scale: compact / standard / large;
- general style hints from the existing allowlist.

These tokens modify only generic layout characteristics such as spacing, headline scale and corner radius. They do not reproduce proprietary styles or assets.

P1 URL and P2 Image/Screenshot previews can now pass their bounded design signals into the same renderer.

## Guardrails

P3 rejects:

- arbitrary operations;
- duplicate operations in one turn;
- hidden/extra action fields;
- stale base state;
- tampered state digests;
- malformed card permutations;
- oversized edit requests;
- direct business identity/contact mutations;
- any widening of Production or customer-commitment authority.

Production publish remains HUMAN_ONLY.

## Non-scope

P3 does not yet provide:

- a live foundation-model conversational adapter;
- arbitrary HTML/CSS editing;
- drag-and-drop editing;
- Production publish;
- payment activation;
- customer acceptance automation.

A later adapter may translate natural-language requests into the bounded P3 action language, but it must not bypass this validator.

## Next capability

After P3 is proven:

**P4 Visual Editor / Structured Controls → same bounded SiteSpec edit state**

The visual editor should call the same edit operations rather than create another mutation engine.
