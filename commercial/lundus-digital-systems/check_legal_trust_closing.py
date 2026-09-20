#!/usr/bin/env python3
from pathlib import Path
import json,sys

root=Path("commercial/lundus-digital-systems")
docs=Path("docs/commercial")
errors=[]

contract=json.loads((root/"legal-trust-contract.json").read_text())
if contract.get("schema")!="lds.legal-trust-readiness/1":
    errors.append("legal-trust schema drift")
if contract.get("production_ready") is not False:
    errors.append("production_ready must remain false")

verified=contract.get("verified_values",{})
for key in ["registered_entity_name","registration_number","final_commercial_domain","registration_status"]:
    if not verified.get(key):
        errors.append(f"verified value missing: {key}")

pending=set(contract.get("pending_verified_values",[]))
expected_pending={
    "official_email","official_phone","official_trade_address_publication_approval",
    "support_complaint_channel","policy_effective_dates"
}
if pending!=expected_pending:
    errors.append(f"pending verified values drift: {sorted(pending)}")

lang=contract.get("language_readiness",{})
for key in ["supplier_disclosure_bm","privacy_notice_bm","terms_bm","refund_cancellation_bm"]:
    if lang.get(key)!="RC_PRESENT":
        errors.append(f"BM readiness missing: {key}")
if lang.get("effective_versions_approved") is not False:
    errors.append("effective versions must remain unapproved")

pack=json.loads((docs/"LDS_LEGAL_TRUST_CLOSING_PACK.json").read_text())
if pack.get("schema")!="lds.legal-trust-closing-pack/1":
    errors.append("closing pack schema drift")
if pack.get("status")!="HOLD":
    errors.append("closing pack must remain HOLD")
if pack.get("production_activation_authorized") is not False:
    errors.append("Production activation must remain false")
if pack.get("live_payment_authorized") is not False:
    errors.append("live payment must remain false")

for page in ["maklumat-urusniaga.html","privacy-bm.html","terms-bm.html","refund-bm.html"]:
    p=root/page
    if not p.is_file():
        errors.append(f"missing BM surface: {page}")
    elif 'lang="ms"' not in p.read_text():
        errors.append(f"BM surface missing lang=ms: {page}")

bm=(root/"maklumat-urusniaga.html").read_text()
for token in ["202603248473 (003891235-V)","lundusdigital.com","BELUM DISAHKAN","BELUM DILULUSKAN"]:
    if token not in bm:
        errors.append(f"BM disclosure missing guard/evidence: {token}")

if errors:
    print("LDS Legal Trust Closing Pack: FAIL")
    for e in errors: print("-",e)
    sys.exit(1)
print("LDS Legal Trust Closing Pack: PASS")
print("legal_trust=HOLD; bm_surfaces=RC_PRESENT; verified_business_particulars=PASS")
