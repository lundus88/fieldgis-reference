import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
policy = json.loads((ROOT / "remediation-policy.json").read_text())

required_human_only = {
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_DEPLOY_OR_RELEASE",
    "PRODUCTION_DATA_MUTATION",
    "AUTHORITY_OR_SECURITY_POLICY_WIDENING",
    "CUSTOMER_OUTREACH",
    "BID_SUBMISSION",
    "QUOTATION_OR_PRICING_COMMITMENT",
    "CONTRACT_OR_LEGAL_COMMITMENT",
    "FINANCIAL_COMMITMENT",
}

assert policy.get("default_decision") == "HOLD"
assert policy["allowed_conditions"]["environment"] == "NON_PRODUCTION"
assert policy["allowed_conditions"]["reversible"] is True
assert policy["allowed_conditions"]["max_risk"] == "LOW"
assert policy["allowed_conditions"]["evidence_required"] is True
assert policy["allowed_conditions"]["independent_revalidation_required"] is True
assert policy["allowed_conditions"]["max_attempts"] == 1
assert required_human_only.issubset(set(policy["human_only_actions"]))
assert "SELF_CERTIFICATION" in policy["forbidden_remediation"]
assert "DELEGATION_WIDENING" in policy["forbidden_remediation"]
assert "EVIDENCE_BYPASS" in policy["forbidden_remediation"]

print("LOM GATE D REMEDIATION POLICY: PASS")
