# LD Email DNS Change Set — Draft

Status: PARTIAL EXACT VALUES CAPTURED — MX / SPF / DKIM STILL PENDING  
Domain: `lundusdigital.com`  
DNS mutation authorized by repository: **NO**

## Exact Zoho record now captured

### READY FOR HUMAN APPLICATION REVIEW
- Type: `TXT`
- Host / Name: `@` (Zoho also states blank is acceptable)
- Value / Content: `zoho-verification=zb36894990.zmverify.zoho.com`
- Purpose: Zoho domain ownership verification

Use the DNS provider's default TTL unless an exact TTL is explicitly supplied by Zoho or an approved DNS policy. Do not infer a TTL from unrelated existing records.

## Evidence-backed current Exabytes zone

### KEEP
- `@  A  103.7.9.22`
- `@  NS  ns184.mschosting.com`
- `@  NS  ns185.mschosting.com`
- `@  NS  ns186.mschosting.com`
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

1. Add only the exact Zoho verification TXT record above.
2. Do not change A/CNAME/NS/MX yet.
3. Wait for DNS propagation.
4. Return to Zoho and click `Verify TXT Record`.
5. After ownership PASS, capture exact Zoho MX, SPF and DKIM values.
6. Generate and approve the final mail-routing change set before replacing the existing MX.
