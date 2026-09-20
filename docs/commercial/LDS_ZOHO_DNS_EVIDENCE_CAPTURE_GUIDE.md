# LD Zoho Mail — Evidence Capture & DNS Change-Set Guide

Status: PREPARED / DNS NOT AUTHORIZED

## Objective

Move the email gate from **provider purchased / channels selected** to **exact provider records captured and review-ready**, without changing DNS yet.

Selected LD channels:
- Commercial: `hello@lundusdigital.com`
- Support / complaints: `support@lundusdigital.com`
- Billing: `billing@lundusdigital.com`

These addresses are selected but are **not yet verified active**.

## Capture from Zoho Admin Console

For `lundusdigital.com`, capture exactly what Zoho displays:

1. Domain verification
   - record type
   - host/name
   - exact value
2. MX
   - every MX host/value
   - priority for each
3. SPF
   - exact TXT host/name
   - exact TXT value
4. DKIM
   - selector
   - exact TXT host/name
   - full public-key TXT value

Do not substitute generic examples from help documentation. Zoho states that MX values can differ according to the data center and that the exact domain values should be taken from the Admin Console.

## DNS review gate

Before applying anything:
- identify where authoritative nameservers currently point;
- export/capture current DNS as rollback evidence;
- check for existing MX/TXT/SPF/DKIM records;
- do not create multiple SPF records;
- do not change `@` / `www` website A/CNAME records as part of the email-only change;
- do not change nameservers unless separately approved;
- compare every proposed record against the Zoho Admin Console evidence;
- obtain explicit human approval for the exact change set.

## After approved DNS application

Verify in this order:

1. domain ownership
2. MX
3. inbound mail to `hello@`
4. outbound mail from `hello@`
5. `support@` alias receive/send behavior
6. `billing@` alias receive/send behavior
7. SPF alignment
8. DKIM alignment
9. prepare DMARC `p=none` only after SPF/DKIM are confirmed

## HOLD rules

Remain HOLD if:
- exact Zoho records are unavailable;
- any record is inferred;
- SPF conflicts exist;
- DKIM is incomplete/truncated;
- authoritative DNS host is uncertain;
- mailbox or aliases cannot be verified;
- human DNS mutation approval has not been recorded.

Website Production domain binding, public payment and public launch remain separate gates.
