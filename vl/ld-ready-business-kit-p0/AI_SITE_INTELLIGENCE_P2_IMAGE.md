# LD AI Site Intelligence P2 — Image/Screenshot Reference to SiteSpec

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

Extend the merged P0 Prompt and P1 URL-reference capabilities with an image/screenshot reference mode while reusing the same SiteSpec contract, Ready Business Kit renderer, QA and Delivery Factory.

Flow:

**Customer image/screenshot → Approved read-only visual analysis → bounded design signals → SiteSpec → Existing Renderer → Preview → Existing QA / Delivery Factory**

## Important boundary

P2 is not a pixel-perfect cloning engine.

The image may contribute only bounded structural/design signals such as:
- section types/order;
- style category;
- layout density;
- sticky navigation;
- floating CTA.

P2 does not copy:
- OCR/body text;
- logos/branding;
- embedded images/assets;
- source code;
- proprietary visual assets.

Customer business facts and actual website content remain separately supplied and validated.

## Evidence contract

P2 requires a bounded image-evidence manifest containing:
- SHA-256 asset digest;
- MIME type;
- dimensions;
- byte size;
- source authority;
- approved structural design signals.

Allowed MIME types:
- image/png
- image/jpeg
- image/webp

Limits:
- maximum file size: 12 MiB;
- maximum single dimension: 12,000 px;
- maximum total pixels: 50 million.

Accepted source-authority labels:
- CUSTOMER_PROVIDED
- CUSTOMER_AUTHORIZED
- REFERENCE_ONLY

## Vision adapter boundary

This PR does not decode image bytes and does not invoke a vision model.

A later approved visual-analysis adapter may inspect an image read-only and produce the bounded evidence manifest. It must:
- preserve SHA-256 provenance;
- never persist secrets from screenshots;
- not emit copied OCR/body text into SiteSpec;
- avoid facial/person identity inference;
- enforce image size/type constraints before analysis;
- fail closed if analysis confidence or source authority is insufficient.

## Reuse / no duplication

P2 extends ld.ai-site-spec/1 and calls the existing P0 compiler and render_preview().

It does not create:
- another renderer;
- another QA engine;
- another Delivery Factory;
- another customer portal;
- another Production deployment system.

The existing visual-preview tooling remains an output QA capability; P2 only defines a controlled input-reference contract.

## Authority

- Production publish: HUMAN_ONLY
- customer/legal/financial commitments: HUMAN_ONLY
- no live vision/API invocation in this PR
- no Production deployment
- no payment activation

## Next capability

After P2 is proven:
**P3 Conversational Editing → SiteSpec patches → Existing Renderer**
