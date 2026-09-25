# LD AI Site Intelligence P1 — URL Reference to SiteSpec

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

Extend the merged P0 Prompt → SiteSpec contract with a safe URL-reference mode while reusing the same Ready Business Kit renderer, QA, Delivery Factory and governance path.

Flow:

**Reference URL → Approved read-only structural capture → SiteSpec design signals → Existing Ready Business Kit Renderer → Preview → Existing QA / Delivery Factory**

## Important boundary

P1 is reference-inspired, not a cloning engine.

The URL may contribute only bounded structural/design signals such as:
- section order/types;
- style category;
- layout density;
- sticky navigation;
- floating CTA.

P1 does not copy:
- third-party body text;
- HTML/CSS/JavaScript;
- source code;
- images or assets.

Customer business facts and vertical content remain separately supplied and validated.

## URL safety

The P1 compiler itself performs no network request.

It accepts only:
- HTTPS references;
- public-looking hostnames or globally routable IP literals;
- no embedded credentials;
- no non-standard port;
- no localhost / .local / direct private IP reference.

Query strings and fragments are stripped before the reference is persisted.

Any future network fetch adapter must additionally:
- resolve DNS and reject private/reserved/link-local destinations after resolution;
- re-check every redirect;
- cap response size and time;
- accept HTML only;
- disable credential forwarding;
- preserve provenance and capture digest.

## Capture contract

The compiler requires an APPROVED_READ_ONLY structural snapshot whose source URL matches the normalized reference URL.

Raw HTML, full body text, CSS, JavaScript, source code, images and assets are explicitly rejected.

## Reuse / no duplication

P1 extends ld.ai-site-spec/1 and calls the existing P0 compiler plus the existing render_preview() path.

It does not create:
- a second website renderer;
- another delivery factory;
- another QA engine;
- another customer portal;
- another deployment system.

## Authority

- Production publish: HUMAN_ONLY
- customer/legal/financial commitments: HUMAN_ONLY
- no live network fetch in this PR
- no Production deployment
- no payment activation

## Next capability

After P1 is proven:
**P2 Image/Screenshot → SiteSpec → Existing Renderer**

The same originality, evidence and authority rules should remain in force.
