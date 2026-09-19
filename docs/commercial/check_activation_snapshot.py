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
if release.get("preview_project_id") != "prj_9areW7U50izhbz8yNrXK2r1YcJ1F":
    errors.append("preview project id drift")
if release.get("preview_deployment_id") != "dpl_F4rugJSSdfWMmUzb6T2ShGSRnZCJ":
    errors.append("current reviewed Preview deployment id drift")
if release.get("preview_state") != "READY":
    errors.append("Preview must be READY in the current snapshot")
if release.get("preview_target") != "preview":
    errors.append("reviewed deployment must remain Preview")
if release.get("preview_visual_qa") != "PASS":
    errors.append("Preview visual QA must be PASS")
if release.get("preview_workflow_qa") != "PASS":
    errors.append("Preview workflow QA must be PASS")

required_gate_sections = {
    "business_licence": "LICENCE_READY",
    "legal_trust": "LEGAL_TRUST_READY",
    "lead_intake": "LIVE_LEAD_INTAKE",
    "payment": "PAYMENT_PRODUCTION_READY",
    "golden_transaction": "GOLDEN_TRANSACTION_PASS",
}
for section, _gate in required_gate_sections.items():
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
    for section in required_gate_sections:
        if data.get(section, {}).get("status") != "HOLD" and section != "golden_transaction":
            errors.append(f"{section} must remain HOLD in the current pre-licence snapshot")
    if data.get("golden_transaction", {}).get("status") != "HOLD":
        errors.append("live Golden Transaction must remain HOLD")
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
    for key in ["official_evidence_id", "evidence_current_as_of"]:
        if not data.get("business_licence", {}).get(key):
            errors.append(f"authorized snapshot missing business licence {key}")
    legal = data.get("legal_trust", {})
    for key in [
        "registered_particulars_evidence_id",
        "privacy_policy_version",
        "terms_policy_version",
        "refund_policy_version",
        "support_channel_evidence_id",
    ]:
        if not legal.get(key):
            errors.append(f"authorized snapshot missing legal/trust {key}")
    if data.get("lead_intake", {}).get("production_activation_authorized") is not True:
        errors.append("authorized snapshot requires lead intake Production authority")
    if not data.get("lead_intake", {}).get("production_config_fingerprint"):
        errors.append("authorized snapshot requires lead-intake config fingerprint")
    if data.get("payment", {}).get("production_activation_authorized") is not True:
        errors.append("authorized snapshot requires payment Production authority")
    if not data.get("payment", {}).get("provider_config_fingerprint"):
        errors.append("authorized snapshot requires payment config fingerprint")
    golden = data.get("golden_transaction", {})
    for key in ["live_transaction_evidence_id", "reconciliation_evidence_id"]:
        if not golden.get(key):
            errors.append(f"authorized snapshot missing Golden Transaction {key}")
    for key in ["approved_by", "approved_at", "expires_at"]:
        if not decision.get(key):
            errors.append(f"authorized snapshot missing decision.{key}")
    if blockers:
        errors.append("authorized snapshot must have no blockers")

required_invalidation_phrases = [
    "artifact or release SHA changes",
    "Preview deployment",
    "business/licence evidence",
    "legal policy",
    "lead-intake Production configuration",
    "payment-provider Production configuration",
    "Golden Transaction",
    "decision expires",
    "mandatory gate returns to HOLD",
]
rules = "\n".join(data.get("invalidation_rules", []))
for phrase in required_invalidation_phrases:
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
print(f"blockers={','.join(blockers)}")
