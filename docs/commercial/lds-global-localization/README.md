# LD Global Localization Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: provide deterministic locale, language, formatting and market-content resolution for supported LD markets without inventing legal, tax, currency or regulatory conclusions.

Resolution flow:
Customer Market → Approved Locale Pack → Language → Currency Display → Date/Time Format → Policy Content Version → Human Market Review

Controls:
- locale packs are versioned and explicitly approved;
- legal, tax and regulatory text cannot be machine-invented;
- currency display does not imply FX conversion authority;
- unsupported locale/market returns FALLBACK_REVIEW;
- customer-facing translations that affect rights, price or obligations require approved source content and review;
- Production locale activation remains separately gated.
