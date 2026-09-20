# LD Usage Metering & Cost Attribution Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: attribute measurable resource usage and cost to the correct customer organization, project and service without turning internal measurements directly into billable customer charges.

Metering domains:
- AI/model/API usage
- hosting/storage
- build/factory runtime
- third-party services
- support/resource consumption

Rules:
- meter only evidence-backed usage;
- keep internal cost attribution separate from customer price;
- stale or missing usage evidence returns REVIEW;
- cross-tenant usage attribution is blocked;
- billing remains governed by approved quotation/subscription terms;
- no automatic customer charge.
