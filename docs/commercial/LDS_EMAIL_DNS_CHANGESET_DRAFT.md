# LD Email DNS Change Set — Draft

Status: EXACT ZOHO MX CAPTURED — SPF / DKIM STILL PENDING  
Domain: `lundusdigital.com`  
General DNS mutation authority: **NO**

## Already applied and retained

- `@ TXT 14440 zoho-verification=zb36894990.zmverify.zoho.com` — Zoho ownership verification
- `@ A 103.7.9.22` — KEEP
- `@ NS ns184.mschosting.com` — KEEP
- `@ NS ns185.mschosting.com` — KEEP
- `@ NS ns186.mschosting.com` — KEEP
- `www CNAME lundusdigital.com` — KEEP
- `ftp CNAME lundusdigital.com` — KEEP
- `mail CNAME lundusdigital.com` — REVIEW SEPARATELY / DO NOT DELETE YET

## MX replacement — exact Zoho values captured

### DELETE
- `@ MX priority 0 lundusdigital.com`

### ADD
- `@ MX priority 10 mx.zoho.com`
- `@ MX priority 20 mx2.zoho.com`
- `@ MX priority 50 mx3.zoho.com`

Use the DNS provider's default TTL unless Zoho supplies an exact TTL.

## Still pending exact Zoho evidence

- SPF TXT value
- DKIM selector / TXT public-key value

## Safe sequence

1. Delete only the existing root MX `0 lundusdigital.com`.
2. Add the three exact Zoho MX records above.
3. Do not change A, NS, CNAME or verification TXT records.
4. Return to Zoho and click `Verify` on the MX page.
5. After MX PASS, capture exact SPF and DKIM values before adding them.
