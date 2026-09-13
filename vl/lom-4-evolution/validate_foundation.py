#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REQUIRED_HUMAN_ONLY = {
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_DEPLOYMENT_OR_RELEASE",
    "PRODUCTION_DATA_MUTATION",
    "AUTHORITY_OR_SECURITY_POLICY_WIDENING",
    "CUSTOMER_OUTREACH",
    "BID_SUBMISSION",
    "QUOTATION_OR_PRICING_COMMITMENT",
    "CONTRACTING_OR_LEGAL_COMMITMENT",
    "FINANCIAL_COMMITMENT",
}


def load(name):
    return json.loads((ROOT / name).read_text())


def validate():
    constitution = load("organization-constitution.json")
    roles = load("agent-role-registry.json")

    assert constitution["default_authority_decision"] == "DENY_OR_HOLD"
    assert REQUIRED_HUMAN_ONLY.issubset(set(constitution["human_only_actions"]))
    assert constitution["delegation_rules"]["may_widen"] is False
    assert constitution["delegation_rules"]["self_delegate_new_authority"] is False
    assert constitution["evidence_rules"]["synthetic_positive_state_forbidden"] is True
    assert constitution["segregation_of_duties"]["builder_may_be_sole_certifier"] is False
    assert constitution["self_remediation"]["production_allowed"] is False
    assert constitution["self_remediation"]["authority_widening_allowed"] is False
    assert constitution["learning"]["may_auto_apply_authority_changes"] is False

    role_ids = {r["id"] for r in roles["roles"]}
    required_roles = {"DIRECTOR", "PLANNER", "EXECUTOR", "VALIDATOR", "RISK_GOVERNOR", "MEMORY_KEEPER"}
    assert required_roles.issubset(role_ids)

    executor = next(r for r in roles["roles"] if r["id"] == "EXECUTOR")
    assert "HUMAN_ONLY_ACTION" in executor["forbidden"]
    validator = next(r for r in roles["roles"] if r["id"] == "VALIDATOR")
    assert "EXECUTE_VALIDATED_CONSEQUENTIAL_WORK" in validator["forbidden"]

    return "LOM 4.0 FOUNDATION: PASS"


if __name__ == "__main__":
    print(validate())
