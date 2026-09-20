# LD Partner / Affiliate / Reseller Engine v1

Status: DEVELOPMENT / NON-PRODUCTION

Purpose: provide an auditable distribution layer for referrals, affiliates and approved resellers without allowing automated commission payout or bypassing LD commercial controls.

Commercial flow:
Partner → Attributed Lead → Qualified Customer → Human-Approved Sale → Eligible Commission → Human Payout Approval

Core controls:
- only approved partners may accrue commission eligibility;
- self-referral, duplicate attribution and suspicious loops return REVIEW;
- refunded, reversed or disputed transactions cannot become final payable commission automatically;
- commission rates come from an approved partner agreement or policy version;
- payout remains human-approved;
- Production partner activation is separately gated.
