# LD Email DNS Change Set — Draft

Status: BLOCKED ON EXACT ZOHO ADMIN CONSOLE VALUES  
Domain: `lundusdigital.com`  
DNS mutation authorized: **NO**

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

Do not delete this record yet. It is not required for Zoho MX activation, but its future purpose should be reviewed after mailbox activation.

### DELETE ONLY WHEN EXACT ZOHO MX IS APPROVED
- `@  MX  priority 0  lundusdigital.com`

This existing MX would conflict with Zoho becoming the authoritative inbound mail route. It must not be removed until the exact Zoho MX replacement set is captured and approved.

### ADD — PENDING EXACT ZOHO EVIDENCE
- Domain verification record
- MX record set and priorities
- SPF TXT value
- DKIM TXT host/value for the exact selector

No generic Zoho example may be substituted.

## Current conflict assessment

- Existing root MX conflict: **YES**
- Existing TXT/SPF conflict evidenced: **NO**
- Existing DKIM TXT conflict evidenced: **NO**
- Website A/CNAME mutation required for email setup: **NO**

## Next evidence required

Capture screenshots from Zoho Mail Admin Console for `lundusdigital.com` showing:
1. Domain Verification
2. MX
3. SPF
4. DKIM

The final change set will be generated only from those exact values.
