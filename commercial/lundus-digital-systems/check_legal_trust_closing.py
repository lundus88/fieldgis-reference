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

expected_pending = {
    "official_phone",
    "official_trade_address_publication_approval",
    "policy_effective_dates",
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
if lang.get("effective_versions_approved") is not False:
    errors.append("effective versions must remain unapproved")

contract_candidates = contract.get("policy_candidates", {})
for key in ["privacy", "terms", "refund_cancellation"]:
    candidate = contract_candidates.get(key, {})
    if candidate.get("version") != "1.0-RC2":
        errors.append(f"contract policy version drift: {key}")
    if candidate.get("human_approved") is not False:
        errors.append(f"contract policy must remain human_approved=false: {key}")
    if candidate.get("effective_date") is not None:
        errors.append(f"contract policy effective date must remain null: {key}")

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
    "OFFICIAL_COMMERCIAL_PHONE_VERIFIED",
    "TRADE_ADDRESS_PUBLICATION_APPROVED",
    "PRIVACY_EFFECTIVE_VERSION_APPROVED",
    "TERMS_EFFECTIVE_VERSION_APPROVED",
    "REFUND_EFFECTIVE_VERSION_APPROVED",
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

for key in ["privacy", "terms", "refund_cancellation"]:
    candidate = pack.get("policy_candidates", {}).get(key, {})
    if candidate.get("version") != "1.0-RC2":
        errors.append(f"closing pack candidate version drift: {key}")
    if candidate.get("status") != "READY_FOR_HUMAN_REVIEW":
        errors.append(f"closing pack candidate not review-ready: {key}")

approval = load_json(docs / "LDS_LEGAL_TRUST_FINAL_APPROVAL.json")
if approval.get("schema") != "lds.legal-trust-final-approval/1":
    errors.append("final approval schema drift")
if approval.get("status") != "HOLD_HUMAN_APPROVAL_REQUIRED":
    errors.append("final approval manifest must remain HOLD_HUMAN_APPROVAL_REQUIRED")
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
    errors.append("official phone must remain null until independently verified")
if phone.get("status") != "HOLD_EVIDENCE_REQUIRED":
    errors.append("official phone must remain HOLD_EVIDENCE_REQUIRED")

address = particulars.get("trade_address", {})
if address.get("value") is not None:
    errors.append("trade address value must not be published in approval manifest")
if address.get("verified_from_registration") is not True:
    errors.append("trade address registration evidence state drift")
if address.get("public_display_approved") is not False:
    errors.append("trade address public display must remain unapproved")
if address.get("status") != "HOLD_PUBLICATION_APPROVAL_REQUIRED":
    errors.append("trade address must remain HOLD_PUBLICATION_APPROVAL_REQUIRED")

approval_candidates = approval.get("policy_candidates", {})
for key in ["privacy", "terms", "refund_cancellation"]:
    candidate = approval_candidates.get(key, {})
    if candidate.get("version") != "1.0-RC2":
        errors.append(f"final approval policy version drift: {key}")
    if candidate.get("human_approved") is not False:
        errors.append(f"final approval policy must remain unapproved: {key}")
    if candidate.get("effective_date") is not None:
        errors.append(f"final approval policy effective date must remain null: {key}")

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
    "Candidate version:",
    "1.0-RC2",
    "pending explicit human approval",
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
    "Versi calon:",
    "1.0-RC2",
    "menunggu kelulusan manusia",
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
    for token in ["Candidate version:", "1.0-RC2", "pending explicit human approval", "support@lundusdigital.com"]:
        if token not in text:
            errors.append(f"{page} candidate guard missing: {token}")

for page in ["terms-bm.html", "refund-bm.html"]:
    text = (root / page).read_text()
    for token in ["Versi calon:", "1.0-RC2", "menunggu kelulusan manusia", "support@lundusdigital.com"]:
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
print("policy_candidates=1.0-RC2_READY_FOR_HUMAN_REVIEW")
print("official_phone=HOLD_EVIDENCE_REQUIRED")
print("trade_address_publication=HOLD")
print("policy_effective_versions=HOLD_HUMAN_APPROVAL_REQUIRED")
