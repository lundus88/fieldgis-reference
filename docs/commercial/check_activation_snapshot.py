#!/usr/bin/env python3
from pathlib import Path
import json
import sys

path = Path("docs/commercial/LDS_ACTIVATION_SNAPSHOT.json")
data = json.loads(path.read_text())
errors = []

if data.get("schema") != "lds.activation-snapshot/1":
    errors.append("unexpected activation snapshot schema")
if data.get("single_use") is not True:
    errors.append("activation snapshot must be single_use=true")

release = data.get("release", {})
if not release.get("commercial_surface_source_sha"):
    errors.append("commercial surface source SHA missing")
if release.get("preview_project") != "lundus-digital-systems-preview":
    errors.append("preview project drift")
if release.get("preview_deployment_id") != "dpl_F4rugJSSdfWMmUzb6T2ShGSRnZCJ":
    errors.append("current reviewed Preview deployment id drift")
if release.get("preview_state") != "READY" or release.get("preview_target") != "preview":
    errors.append("reviewed Preview state/target drift")
if release.get("preview_visual_qa") != "PASS" or release.get("preview_workflow_qa") != "PASS":
    errors.append("Preview QA must remain PASS")

domain_email = data.get("domain_email", {})
if domain_email.get("manifest") != "docs/commercial/LDS_DOMAIN_EMAIL_READINESS.json":
    errors.append("domain/email readiness manifest missing or drifted")
if domain_email.get("final_commercial_domain") != "lundusdigital.com":
    errors.append("final commercial domain drift")
if domain_email.get("domain_ownership") != "PASS":
    errors.append("domain ownership evidence must be PASS")
if domain_email.get("email_provider") != "Zoho Mail" or domain_email.get("email_plan") != "Mail Lite 10 GB":
    errors.append("email provider/plan drift")
if domain_email.get("email_subscription_status") != "PASS":
    errors.append("email subscription evidence must be PASS")

required_gate_sections = {
    "business_licence": "LICENCE_READY",
    "legal_trust": "LEGAL_TRUST_READY",
    "domain_email": "DOMAIN_EMAIL_READY",
    "lead_intake": "LIVE_LEAD_INTAKE",
    "payment": "PAYMENT_PRODUCTION_READY",
    "golden_transaction": "GOLDEN_TRANSACTION_PASS",
}
for section in required_gate_sections:
    if section not in data:
        errors.append(f"missing activation section: {section}")

decision = data.get("decision", {})
authorized = decision.get("launch_authorized")
status = data.get("snapshot_status")
blockers = data.get("blockers", [])

if authorized is False:
    if status != "HOLD_NOT_FORMED":
        errors.append("non-authorized snapshot must be HOLD_NOT_FORMED")
    if not blockers:
        errors.append("HOLD snapshot must list blockers")

    for section, gate in required_gate_sections.items():
        section_status = data.get(section, {}).get("status")
        if section_status not in {"PASS","HOLD"}:
            errors.append(f"{section} must be PASS or HOLD")
        if section_status == "HOLD" and gate not in blockers:
            errors.append(f"HOLD section missing blocker: {gate}")
        if section_status == "PASS" and gate in blockers:
            errors.append(f"PASS section must not remain blocker: {gate}")

    business = data.get("business_licence", {})
    if business.get("status") == "PASS":
        for key in ["official_evidence_id","evidence_current_as_of","valid_through"]:
            if not business.get(key):
                errors.append(f"PASS business licence missing {key}")

    if domain_email.get("dns_production_binding") != "HOLD":
        errors.append("DNS Production binding must remain HOLD")
    if domain_email.get("email_dns_authentication") != "PASS":
        errors.append("email DNS authentication must remain PASS after verified UAT")
    if domain_email.get("official_commercial_email") != "PASS":
        errors.append("official commercial email must remain PASS after verified UAT")
    if domain_email.get("support_complaint_channel") != "PASS_INBOUND":
        errors.append("support complaint channel must remain PASS_INBOUND")
    if domain_email.get("production_config_fingerprint") is not None:
        errors.append("domain/email Production fingerprint must remain null")
    if data.get("lead_intake", {}).get("production_activation_authorized") is not False:
        errors.append("live lead intake must not be authorized")
    if data.get("payment", {}).get("production_activation_authorized") is not False:
        errors.append("Production payment must not be authorized")
else:
    if authorized is not True:
        errors.append("launch_authorized must be boolean")
    if status != "AUTHORIZED":
        errors.append("authorized launch must use snapshot_status=AUTHORIZED")
    for section in required_gate_sections:
        if data.get(section, {}).get("status") != "PASS":
            errors.append(f"authorized snapshot requires {section}=PASS")
    if blockers:
        errors.append("authorized snapshot must have no blockers")

rules = "\n".join(data.get("invalidation_rules", []))
for phrase in [
    "artifact or release SHA changes",
    "Preview deployment",
    "business/licence evidence",
    "domain ownership/DNS/email",
    "legal policy",
    "lead-intake Production configuration",
    "payment-provider Production configuration",
    "Golden Transaction",
    "decision expires",
    "mandatory gate returns to HOLD",
]:
    if phrase not in rules:
        errors.append(f"missing invalidation rule: {phrase}")

if "Evidence existence is not activation authority." not in data.get("rule", ""):
    errors.append("activation-authority separation rule missing")

if errors:
    print("LDS activation snapshot: FAIL")
    for error in errors:
        print("-", error)
    sys.exit(1)

print("LDS activation snapshot: PASS")
print(f"snapshot_status={status}")
print(f"launch_authorized={authorized}")
print(f"business_licence={data.get('business_licence',{}).get('status')}")
print(f"blockers={','.join(blockers)}")
