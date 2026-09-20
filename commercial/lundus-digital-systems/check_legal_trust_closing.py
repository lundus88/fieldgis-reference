#!/usr/bin/env python3
from pathlib import Path
import json
import sys

root = Path("commercial/lundus-digital-systems")
docs = Path("docs/commercial")
errors = []

def load_json(path: Path):
    if not path.is_file():
        errors.append(f"missing JSON evidence: {path}")
        return {}
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        errors.append(f"invalid JSON {path}: {exc}")
        return {}

contract = load_json(root / "legal-trust-contract.json")
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
if verified.get("official_phone_evidence_status") != "VERIFIED_PRESENT_VALUE_REDACTED":
    errors.append("official phone SSM evidence must be verified and redacted")
if verified.get("trade_address_evidence_status") != "VERIFIED_PRESENT_VALUE_REDACTED":
    errors.append("trade address SSM evidence must be verified and redacted")

expected_pending = {
    "ld_dedicated_business_phone",
    "ld_public_business_address",
}
pending = set(contract.get("pending_verified_values", []))
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
if lang.get("effective_versions_approved") is not True:
    errors.append("effective versions must be approved")
effective_versions = lang.get("effective_versions", {})
for key in ["privacy", "terms", "refund_cancellation"]:
    if effective_versions.get(key) != "1.0":
        errors.append(f"effective policy version drift: {key}")
if effective_versions.get("effective_date") != "2026-09-20":
    errors.append("effective policy date drift")

contract_candidates = contract.get("policy_candidates", {})
for key in ["privacy", "terms", "refund_cancellation"]:
    candidate = contract_candidates.get(key, {})
    if candidate.get("version") != "1.0":
        errors.append(f"contract policy version drift: {key}")
    if candidate.get("human_approved") is not True:
        errors.append(f"contract policy must be human_approved=true: {key}")
    if candidate.get("effective_date") != "2026-09-20":
        errors.append(f"contract policy effective date drift: {key}")
    if candidate.get("approved_from") != "1.0-RC2":
        errors.append(f"contract policy approval lineage drift: {key}")

domain = load_json(docs / "LDS_DOMAIN_EMAIL_READINESS.json")
gates = domain.get("gate_status", {})
if gates.get("OFFICIAL_COMMERCIAL_EMAIL") != "PASS":
    errors.append("domain/email evidence must show OFFICIAL_COMMERCIAL_EMAIL PASS")
if gates.get("SUPPORT_COMPLAINT_CHANNEL") != "PASS_INBOUND":
    errors.append("domain/email evidence must show SUPPORT_COMPLAINT_CHANNEL PASS_INBOUND")
if gates.get("EMAIL_DNS_AUTHENTICATION") != "PASS":
    errors.append("email DNS authentication must remain PASS")
if gates.get("LEGAL_TRUST_READY") != "HOLD":
    errors.append("LEGAL_TRUST_READY must remain HOLD until remaining blockers close")

expected_blockers = {
    "LD_DEDICATED_BUSINESS_PHONE_VERIFIED",
    "LD_PUBLIC_BUSINESS_ADDRESS_VALIDATED",
}

pack = load_json(docs / "LDS_LEGAL_TRUST_CLOSING_PACK.json")
if pack.get("schema") != "lds.legal-trust-closing-pack/1":
    errors.append("closing pack schema drift")
if pack.get("status") != "HOLD":
    errors.append("closing pack must remain HOLD")
if pack.get("final_approval_manifest") != "docs/commercial/LDS_LEGAL_TRUST_FINAL_APPROVAL.json":
    errors.append("closing pack final approval manifest link drift")
for key in ["production_activation_authorized", "live_payment_authorized", "public_launch_authorized"]:
    if pack.get(key) is not False:
        errors.append(f"closing pack authority must remain false: {key}")
if set(pack.get("remaining_blockers", [])) != expected_blockers:
    errors.append("remaining legal/trust blocker set drift")

pack_verified = pack.get("verified", {})
if pack_verified.get("official_commercial_email") != "hello@lundusdigital.com":
    errors.append("closing pack official email drift")
if pack_verified.get("support_complaint_channel") != "support@lundusdigital.com":
    errors.append("closing pack support channel drift")
if pack_verified.get("commercial_phone_evidence") != "SSM_FORM_A_VERIFIED_PRESENT_VALUE_REDACTED":
    errors.append("closing pack phone evidence must remain verified/redacted")
if pack_verified.get("trade_address_evidence") != "SSM_BUSINESS_INFO_VERIFIED_PRESENT_VALUE_REDACTED":
    errors.append("closing pack trade address evidence must remain verified/redacted")

for key in ["privacy", "terms", "refund_cancellation"]:
    candidate = pack.get("policy_candidates", {}).get(key, {})
    if candidate.get("version") != "1.0":
        errors.append(f"closing pack approved version drift: {key}")
    if candidate.get("status") != "APPROVED_EFFECTIVE":
        errors.append(f"closing pack policy must be APPROVED_EFFECTIVE: {key}")
    if candidate.get("effective_date") != "2026-09-20":
        errors.append(f"closing pack policy effective-date drift: {key}")

contact_policy = load_json(docs / "LDS_PUBLIC_CONTACT_SEPARATION_POLICY.json")
if contact_policy.get("schema") != "lds.public-contact-separation-policy/1":
    errors.append("public contact separation policy schema drift")
if contact_policy.get("decision_status") != "APPROVED":
    errors.append("public contact separation policy must be APPROVED")
if contact_policy.get("public_identity_strategy") != "SEPARATE_BUSINESS_CONTACTS":
    errors.append("public identity strategy drift")
decisions = contact_policy.get("decisions", {})
if decisions.get("ssm_registered_phone", {}).get("use_as_public_ld_phone") is not False:
    errors.append("SSM phone must not be public LD phone")
if decisions.get("ssm_trade_address", {}).get("publish_as_public_ld_address") is not False:
    errors.append("SSM trade address must not be public LD address")
if contact_policy.get("legal_trust_ready") is not False:
    errors.append("contact policy must keep legal_trust_ready=false")
for key in ["production_activation_authorized","live_payment_authorized","public_launch_authorized"]:
    if contact_policy.get(key) is not False:
        errors.append(f"contact policy authority must remain false: {key}")

approval = load_json(docs / "LDS_LEGAL_TRUST_FINAL_APPROVAL.json")
if approval.get("schema") != "lds.legal-trust-final-approval/1":
    errors.append("final approval schema drift")
if approval.get("status") != "HOLD_SEPARATE_PUBLIC_CONTACTS_REQUIRED":
    errors.append("final approval manifest must remain HOLD_SEPARATE_PUBLIC_CONTACTS_REQUIRED")
if approval.get("legal_trust_ready") is not False:
    errors.append("final approval manifest must keep legal_trust_ready=false")
for key in ["production_activation_authorized", "live_payment_authorized", "public_launch_authorized"]:
    if approval.get(key) is not False:
        errors.append(f"final approval authority must remain false: {key}")
if set(approval.get("remaining_human_decisions", [])) != expected_blockers:
    errors.append("final approval human decision set drift")

particulars = approval.get("commercial_particulars", {})
if particulars.get("official_email", {}).get("value") != "hello@lundusdigital.com":
    errors.append("final approval official email drift")
if particulars.get("official_email", {}).get("status") != "PASS":
    errors.append("final approval official email status drift")
if particulars.get("support_complaint_channel", {}).get("value") != "support@lundusdigital.com":
    errors.append("final approval support channel drift")
if particulars.get("support_complaint_channel", {}).get("status") != "PASS_INBOUND":
    errors.append("final approval support channel status drift")

phone = particulars.get("official_phone", {})
if phone.get("value") is not None:
    errors.append("public LD phone must remain unset until a dedicated business line is verified")
if phone.get("source_strategy") != "SEPARATE_LD_BUSINESS_PHONE":
    errors.append("official phone source strategy drift")
if phone.get("ssm_value_public_use_approved") is not False:
    errors.append("SSM phone must remain not approved for public use")
if phone.get("ssm_value_rejected_for_public_identity") is not True:
    errors.append("SSM phone must remain rejected for public LD identity")
if phone.get("status") != "HOLD_PROVISION_AND_VERIFY":
    errors.append("dedicated LD phone must remain HOLD_PROVISION_AND_VERIFY")

address = particulars.get("trade_address", {})
if address.get("value") is not None:
    errors.append("public LD business address must remain unset until a separate address is validated")
if address.get("source_strategy") != "SEPARATE_PUBLIC_BUSINESS_ADDRESS":
    errors.append("trade address source strategy drift")
if address.get("ssm_value_public_display_approved") is not False:
    errors.append("SSM trade address must remain not approved for public display")
if address.get("ssm_value_rejected_for_public_identity") is not True:
    errors.append("SSM trade address must remain rejected for public LD identity")
if address.get("overlaps_owner_residential_information") is not True:
    errors.append("trade address residential-overlap privacy signal missing")
if address.get("status") != "HOLD_IDENTIFY_VALIDATE_AND_APPROVE":
    errors.append("separate public business address must remain HOLD_IDENTIFY_VALIDATE_AND_APPROVE")

approval_candidates = approval.get("policy_candidates", {})
for key in ["privacy", "terms", "refund_cancellation"]:
    candidate = approval_candidates.get(key, {})
    if candidate.get("version") != "1.0":
        errors.append(f"final approval policy version drift: {key}")
    if candidate.get("human_approved") is not True:
        errors.append(f"final approval policy must be approved: {key}")
    if candidate.get("effective_date") != "2026-09-20":
        errors.append(f"final approval policy effective date drift: {key}")
    if candidate.get("approved_from") != "1.0-RC2":
        errors.append(f"final approval policy lineage drift: {key}")

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

privacy_en = (root / "privacy.html").read_text()
for token in [
    "Version:",
    "1.0",
    "Effective date:",
    "20 September 2026",
    "Personal data we may collect",
    "Sources of personal data",
    "Purposes of processing",
    "Whether providing data is mandatory",
    "Disclosure to third parties",
    "Cookies, analytics and technical data",
    "Cross-border processing",
    "Security and retention",
    "Your rights and choices",
    "Marketing",
    "Changes to this notice",
    "Enquiries and complaints",
]:
    if token not in privacy_en:
        errors.append(f"privacy EN candidate missing: {token}")

privacy_bm = (root / "privacy-bm.html").read_text()
for token in [
    "Versi:",
    "1.0",
    "Tarikh kuat kuasa:",
    "20 September 2026",
    "Data peribadi yang mungkin dikumpul",
    "Sumber data peribadi",
    "Tujuan pemprosesan",
    "Sama ada pemberian data adalah wajib",
    "Pendedahan kepada pihak ketiga",
    "Cookies, analitik dan data teknikal",
    "Pemprosesan rentas sempadan",
    "Keselamatan dan penyimpanan",
    "Hak dan pilihan anda",
    "Pemasaran",
    "Perubahan kepada notis ini",
    "Pertanyaan dan aduan",
]:
    if token not in privacy_bm:
        errors.append(f"privacy BM candidate missing: {token}")

for page in ["terms.html", "refund.html"]:
    text = (root / page).read_text()
    for token in ["Version:", "1.0", "Effective date:", "20 September 2026", "support@lundusdigital.com"]:
        if token not in text:
            errors.append(f"{page} candidate guard missing: {token}")

for page in ["terms-bm.html", "refund-bm.html"]:
    text = (root / page).read_text()
    for token in ["Versi:", "1.0", "Tarikh kuat kuasa:", "20 September 2026", "support@lundusdigital.com"]:
        if token not in text:
            errors.append(f"{page} BM candidate guard missing: {token}")

if errors:
    print("LDS Legal Trust Closing Pack: FAIL")
    for error in errors:
        print("-", error)
    sys.exit(1)

print("LDS Legal Trust Closing Pack: PASS")
print("legal_trust=HOLD")
print("official_email=PASS")
print("support_channel=PASS_INBOUND")
print("policy_versions=1.0_APPROVED_EFFECTIVE_2026-09-20")
print("dedicated_ld_phone=HOLD_PROVISION_AND_VERIFY")
print("separate_public_business_address=HOLD_IDENTIFY_VALIDATE_AND_APPROVE")
print("policy_effective_versions=PASS")
