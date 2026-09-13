import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text())


def test_unknown_authority_fails_closed():
    c = load("organization-constitution.json")
    assert c["default_authority_decision"] == "DENY_OR_HOLD"


def test_no_self_authority_widening():
    c = load("organization-constitution.json")
    assert c["delegation_rules"]["may_widen"] is False
    assert c["delegation_rules"]["self_delegate_new_authority"] is False


def test_production_and_money_remain_human_only():
    c = load("organization-constitution.json")
    actions = set(c["human_only_actions"])
    assert "PRODUCTION_DEPLOYMENT_OR_RELEASE" in actions
    assert "PRODUCTION_DATA_MUTATION" in actions
    assert "FINANCIAL_COMMITMENT" in actions
    assert "CONTRACTING_OR_LEGAL_COMMITMENT" in actions


def test_builder_cannot_self_certify():
    c = load("organization-constitution.json")
    assert c["segregation_of_duties"]["builder_may_be_sole_certifier"] is False


def test_self_remediation_is_bounded():
    c = load("organization-constitution.json")
    r = c["self_remediation"]
    assert r["allowed"] is True
    assert r["production_allowed"] is False
    assert r["authority_widening_allowed"] is False
    assert r["financial_or_contractual_actions_allowed"] is False


def test_executor_cannot_take_human_only_actions():
    roles = load("agent-role-registry.json")["roles"]
    executor = next(r for r in roles if r["id"] == "EXECUTOR")
    assert "HUMAN_ONLY_ACTION" in executor["forbidden"]
    assert "SELF_APPROVE" in executor["forbidden"]
