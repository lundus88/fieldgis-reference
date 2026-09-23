# LD FinanceBridge — Provider Sandbox Onboarding

Status: HUMAN ACTION REQUIRED

This runbook is intentionally provider-neutral.

## Before selecting a provider

Verify:
- lawful commercial use;
- API/sandbox availability;
- e-Invoice/MyInvois capability where required;
- authentication model;
- tenant/company selection model;
- documented rate limits;
- webhook/callback authenticity;
- data export and exit path;
- pricing and support terms.

## Required sandbox information

Obtain from the selected provider:
- sandbox login/account;
- sandbox base URL;
- API access token or equivalent credential;
- tenant/company identifier if required;
- tenant header name if required;
- documented request rate limit;
- exact API route documentation;
- e-Invoice validation semantics;
- support contact and escalation path.

## Runtime configuration

Do not commit provider credentials or vendor-specific production configuration to GitHub.

Configure only in the authorised runtime environment:

`LD_FINANCEBRIDGE_ENV=staging`

`LD_FINANCEBRIDGE_ACCESS_TOKEN=<sandbox token>`

`LD_FINANCEBRIDGE_BASE_URL=<sandbox API base URL>`

`LD_FINANCEBRIDGE_TENANT_HEADER=<optional tenant header name>`

`LD_FINANCEBRIDGE_TENANT_KEY=<optional tenant/company key>`

`LD_FINANCEBRIDGE_RATE_LIMIT_PER_MINUTE=<documented provider limit>`

## Gate

The connector remains HOLD until exact API routes and schemas are independently verified and the provider sandbox Golden Transaction passes.

Provider names are implementation details, not LD product branding.
