# LD Email DNS Change Set — Draft

Status: DOMAIN VERIFICATION TXT APPLIED — ZOHO CONFIRMATION + MX / SPF / DKIM PENDING  
Domain: `lundusdigital.com`  
General DNS mutation authority: **NO**

## Applied with human action

### Zoho ownership verification TXT
- Type: `TXT`
- Host / Name: `@`
- TTL: `14440`
- Value: `zoho-verification=zb36894990.zmverify.zoho.com`
- Exabytes evidence: **PRESENT**
- Zoho verification: **PENDING**

Do not edit or remove this record until Zoho ownership verification has passed.

## Evidence-backed current Exabytes zone

### KEEP
- `@  A  103.7.9.22`
- `@  NS  ns184.mschosting.com`
- `@  NS  ns185.mschosting.com`
- `@  NS  ns186.mschosting.com`
- `@  TXT  zoho-verification=zb36894990.zmverify.zoho.com`
- `www  CNAME  lundusdigital.com`
- `ftp  CNAME  lundusdigital.com`

### REVIEW SEPARATELY
- `mail  CNAME  lundusdigital.com`

### DELETE ONLY WHEN EXACT ZOHO MX IS APPROVED
- `@  MX  priority 0  lundusdigital.com`

### ADD — STILL PENDING EXACT ZOHO EVIDENCE
- Zoho MX records with exact priorities
- Single SPF TXT policy containing the exact authorized Zoho sender include/value
- DKIM TXT record for the exact LD selector/public key

No generic Zoho example may be substituted.

## Safe sequence now

1. Return to Zoho Mail Admin Console.
2. Click `Verify TXT Record`.
3. If Zoho does not detect it yet, do not edit the DNS record; allow propagation and retry.
4. After ownership PASS, capture exact Zoho MX values/priorities.
5. Capture exact SPF and DKIM values.
6. Generate and approve the final mail-routing change set before replacing the existing MX.
