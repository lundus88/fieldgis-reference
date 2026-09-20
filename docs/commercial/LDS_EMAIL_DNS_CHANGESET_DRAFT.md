# LD Email DNS Change Set — As-Built Verification

Status: **EMAIL DNS APPLIED AND VERIFIED**  
Domain: `lundusdigital.com`  
Provider: **Zoho Mail**  
General DNS mutation authority: **NO FURTHER CHANGE AUTHORIZED**

## Verified live email records

- `@ TXT zoho-verification=zb36894990.zmverify.zoho.com` — Zoho domain ownership **PASS**
- `@ MX 10 mx.zoho.com` — **PASS**
- `@ MX 20 mx2.zoho.com` — **PASS**
- `@ MX 50 mx3.zoho.com` — **PASS**
- `@ TXT v=spf1 include:zohomail.com ~all` — SPF **PASS**
- `ld2026._domainkey TXT <provider-issued public key>` — DKIM **PASS**
  - The exact public-key value is intentionally not reconstructed from screenshot evidence in this repository.
- `_dmarc TXT v=DMARC1; p=none; rua=mailto:dmarc@lundusdigital.com; ruf=mailto:dmarc@lundusdigital.com; sp=none; adkim=r; aspf=r; pct=100` — DMARC **PASS**

## External UAT evidence

A message from `LUNDUS DIGITAL SYSTEMS <hello@lundusdigital.com>` was delivered to Gmail and Gmail's **Show original** reported:

- SPF: **PASS**
- DKIM: **PASS** for `lundusdigital.com`
- DMARC: **PASS**
- Delivery: **PASS**
- Observed delivery latency: approximately 3 seconds
- Sender display name: **LUNDUS DIGITAL SYSTEMS**

## Alias routing UAT

- `support@lundusdigital.com` → primary inbox `hello@lundusdigital.com`: **PASS**
- `billing@lundusdigital.com` → primary inbox `hello@lundusdigital.com`: **PASS**
- `dmarc@lundusdigital.com` → primary inbox `hello@lundusdigital.com`: **PASS**

Outbound **Send As** for `support@` and `billing@` has not yet been tested and is not required to classify the basic email UAT as PASS.

## Preserved website/DNS scope

Existing website-related A, NS and CNAME records remain outside this email UAT. No Production website binding or public-launch authority is granted by this document.

## DMARC operating posture

DMARC remains at `p=none` for monitoring. Do not strengthen to `quarantine` or `reject` until all legitimate senders, including Zoho and Resend, have been inventoried and SPF/DKIM alignment is verified for those senders.

## Governance

This file is an **as-built verification record**, not a standing authorization for future DNS changes.

- Further DNS mutation: **HOLD / explicit human approval required**
- Production website binding: **HOLD**
- Payment activation: **HOLD**
- Public launch: **HOLD**
