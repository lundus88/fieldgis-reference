# LD AI Site Intelligence P0 — Prompt to Website

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

Add a thin AI-site intelligence layer in front of the existing LD Ready Business Kit without creating a second renderer, delivery factory, QA engine, customer portal or deployment system.

Flow:

**Customer Prompt + Verified Business Facts → SiteSpec → Existing Ready Business Kit Renderer → Preview → Existing QA / Delivery Factory**

## P0 contract

P0 introduces a deterministic `ld.ai-site-spec/1` contract.

It accepts:
- a natural-language prompt;
- verified business name and WhatsApp contact;
- an explicit or unambiguous supported vertical;
- structured vertical content already supplied by the customer.

It produces:
- a bounded SiteSpec;
- normalized onboarding data compatible with the existing renderer;
- a preview through the existing `render_preview()` function.

## Why deterministic first

This PR establishes the contract and safety boundary before binding a foundation model. A later adapter may use a model to propose SiteSpec fields, but the model must not:
- invent business facts;
- copy third-party proprietary text/assets;
- bypass onboarding validation;
- publish to Production;
- create customer/legal/financial commitments.

## Supported P0 verticals

1. Cafe / F&B
2. Homestay
3. Tutor / Education

## Explicit non-scope

P0 does NOT yet implement:
- URL → website;
- screenshot/image → website;
- drag-and-drop editor;
- autonomous Production deploy;
- live model/API invocation.

Those are subsequent capabilities and should extend this SiteSpec contract rather than duplicate the existing LD/VL stack.
