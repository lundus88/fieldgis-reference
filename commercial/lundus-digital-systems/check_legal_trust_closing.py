#!/usr/bin/env python3
from pathlib import Path
import json, sys

root = Path("commercial/lundus-digital-systems")
docs = Path("docs/commercial")
errors = []

contract = json.loads((root / "legal-trust-contract.json").read_text())
if contract.get("schema") != "lds.legal-trust-readiness/1":
    errors.append("legal-trust schema drift")
if contract.get("production_ready") is not False:
    errors.append("production_ready must remain false")

verified = contract.get("verified_values", {})
for key in [
    "registered_entity_name",
    "registration_number",
    "final_commercial_domain",
    "registration_status",
    "official_email",
    "support_complaint_channel",
]:
    if not verified.get(key):
        errors.append(f"verified value missing: {key}")
if verified.get("official_email") != "hello@lundusdigital.com":
    errors.append("official email drift")
if verified.get("official_email_status") != "PASS":
    errors.append("official email evidence must be PASS")
if verified.get("support_complaint_channel") != "support@lundusdigital.com":
    errors.append("support channel drift")
if verified.get("support_complaint_channel_status") != "PASS_INBOUND":
    errors.append("support channel evidence must be PASS_INBOUND")

pending = set(contract.get("pending_verified_values", []))
expected_pending = {
    "official_phone",
    "official_trade_address_publication_approval",
    "policy_effective_dates",
}
if pending != expected_pending:
    errors.append(f"pending verified values drift: {sorted(pending)}")

lang = contract.get("language_readiness", {})
for key in [
    "supplier_disclosure_bm",
    "privacy_notice_bm",
    "terms_bm",
    "refund_cancellation_bm",
]:
    if lang.get(key) != "RC_PRESENT":
        errors.append(f"BM readiness missing: {key}")
if lang.get("effective_versions_approved") is not False:
    errors.append("effective versions must remain unapproved")

domain = json.loads((docs / "LDS_DOMAIN_EMAIL_READINESS.json").read_text())
gates = domain.get("gate_status", {})
if gates.get("OFFICIAL_COMMERCIAL_EMAIL") != "PASS":
    errors.append("domain/email evidence must show OFFICIAL_COMMERCIAL_EMAIL PASS")
if gates.get("SUPPORT_COMPLAINT_CHANNEL") != "PASS_INBOUND":
    errors.append("domain/email evidence must show SUPPORT_COMPLAINT_CHANNEL PASS_INBOUND")
if gates.get("EMAIL_DNS_AUTHENTICATION") != "PASS":
    errors.append("email DNS authentication must remain PASS")
if gates.get("LEGAL_TRUST_READY") != "HOLD":
    errors.append("LEGAL_TRUST_READY must remain HOLD until remaining blockers close")

pack = json.loads((docs / "LDS_LEGAL_TRUST_CLOSING_PACK.json").read_text())
if pack.get("schema") != "lds.legal-trust-closing-pack/1":
    errors.append("closing pack schema drift")
if pack.get("status") != "HOLD":
    errors.append("closing pack must remain HOLD")
if pack.get("production_activation_authorized") is not False:
    errors.append("Production activation must remain false")
if pack.get("live_payment_authorized") is not False:
    errors.append("live payment must remain false")
if pack.get("public_launch_authorized") is not False:
    errors.append("public launch must remain false")

expected_blockers = {
    "OFFICIAL_COMMERCIAL_PHONE_VERIFIED",
    "TRADE_ADDRESS_PUBLICATION_APPROVED",
    "PRIVACY_EFFECTIVE_VERSION_APPROVED",
    "TERMS_EFFECTIVE_VERSION_APPROVED",
    "REFUND_EFFECTIVE_VERSION_APPROVED",
}
if set(pack.get("remaining_blockers", [])) != expected_blockers:
    errors.append("remaining legal/trust blocker set drift")

pack_verified = pack.get("verified", {})
if pack_verified.get("official_commercial_email") != "hello@lundusdigital.com":
    errors.append("closing pack official email drift")
if pack_verified.get("support_complaint_channel") != "support@lundusdigital.com":
    errors.append("closing pack support channel drift")

for page in [
    "maklumat-urusniaga.html",
    "privacy-bm.html",
    "terms-bm.html",
    "refund-bm.html",
]:
    p = root / page
    if not p.is_file():
        errors.append(f"missing BM surface: {page}")
    elif 'lang="ms"' not in p.read_text():
        errors.append(f"BM surface missing lang=ms: {page}")

bm = (root / "maklumat-urusniaga.html").read_text()
for token in [
    "202603248473 (003891235-V)",
    "lundusdigital.com",
    "hello@lundusdigital.com",
    "support@lundusdigital.com",
    "Nombor telefon rasmi: <strong>BELUM DISAHKAN</strong>",
    "BELUM DILULUSKAN",
]:
    if token not in bm:
        errors.append(f"BM disclosure missing guard/evidence: {token}")

if errors:
    print("LDS Legal Trust Closing Pack: FAIL")
    for error in errors:
        print("-", error)
    sys.exit(1)

print("LDS Legal Trust Closing Pack: PASS")
print("legal_trust=HOLD")
print("official_email=PASS")
print("support_channel=PASS_INBOUND")
print("remaining_blockers=phone,address_publication,policy_effective_versions")
