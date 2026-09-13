#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REQUIRED = [
    "portfolio-registry.schema.json",
    "evidence-record.schema.json",
    "authority-matrix.json",
    "exception-queue.schema.json",
    "executive-snapshot.schema.json",
]

HUMAN_ONLY_ACTIONS = {
    "MERGE_PROTECTED_MAIN",
    "PRODUCTION_DEPLOY",
    "PRODUCTION_DATA_MUTATION",
    "PRODUCTION_AUTHORITY_CHANGE",
    "FINANCIAL_OR_CONTRACTUAL_COMMITMENT",
}


def load(name):
    return json.loads((ROOT / name).read_text())


def fail(msg):
    raise SystemExit(f"LOM_CONTROL_PLANE_INVALID: {msg}")


def main():
    for name in REQUIRED:
        path = ROOT / name
        if not path.exists():
            fail(f"missing {name}")
        try:
            json.loads(path.read_text())
        except Exception as exc:
            fail(f"invalid JSON in {name}: {exc}")

    portfolio = load("portfolio-registry.schema.json")
    evidence = load("evidence-record.schema.json")
    authority = load("authority-matrix.json")
    exceptions = load("exception-queue.schema.json")
    executive = load("executive-snapshot.schema.json")

    project = portfolio.get("$defs", {}).get("project", {})
    props = project.get("properties", {})
    health = set(props.get("health", {}).get("enum", []))
    maturity = set(props.get("evidence_maturity", {}).get("enum", []))
    stages = set(props.get("stage", {}).get("enum", []))

    expected_health = {"HEALTHY", "REVIEW", "BLOCKED", "HOLD", "RELEASE_CANDIDATE"}
    expected_maturity = {"CONTRACT_PROVEN", "INTEGRATED", "RUNTIME_PROVEN"}
    if health != expected_health:
        fail("portfolio health enum mismatch")
    if maturity != expected_maturity:
        fail("evidence maturity enum mismatch")
    if "RELEASE_CANDIDATE" not in stages:
        fail("release candidate stage missing")

    all_of = project.get("allOf", [])
    rc_rule = None
    for rule in all_of:
        if rule.get("if", {}).get("properties", {}).get("health", {}).get("const") == "RELEASE_CANDIDATE":
            rc_rule = rule
            break
    if not rc_rule:
        fail("release candidate conditional rule missing")
    then = rc_rule.get("then", {})
    if "evidence_refs" not in then.get("required", []):
        fail("release candidate does not require evidence_refs")
    if "approval_required" not in then.get("required", []):
        fail("release candidate does not require approval_required")
    if then.get("properties", {}).get("approval_required", {}).get("const") is not True:
        fail("release candidate approval_required is not fixed true")

    ev_props = evidence.get("properties", {})
    ev_types = set(ev_props.get("evidence_type", {}).get("enum", []))
    if not {"QA", "SECURITY", "CERTIFICATION", "APPROVAL", "RELEASE", "AUDIT"}.issubset(ev_types):
        fail("critical evidence types missing")
    if "actor" not in evidence.get("required", []):
        fail("evidence actor attribution missing")

    rules = {r.get("action"): r for r in authority.get("rules", [])}
    if authority.get("default_decision") != "DENY_OR_HOLD":
        fail("unknown authority is not fail-closed")
    for action in HUMAN_ONLY_ACTIONS:
        rule = rules.get(action)
        if not rule:
            fail(f"authority rule missing for {action}")
        if rule.get("authority") != "HUMAN_APPROVAL":
            fail(f"{action} is not human-gated")
        if rule.get("evidence_required") is not True:
            fail(f"{action} does not require evidence")

    inv = authority.get("invariants", {})
    if inv.get("production_approval_human_only") is not True:
        fail("production approval is not human-only")
    if inv.get("builder_self_certification_allowed") is not False:
        fail("builder self-certification not prohibited")
    if inv.get("delegation_may_widen_scope") is not False:
        fail("delegation widening not prohibited")
    if inv.get("unknown_authority_allowed") is not False:
        fail("unknown authority allowed")

    ex_props = exceptions.get("$defs", {}).get("exception", {}).get("properties", {})
    categories = set(ex_props.get("category", {}).get("enum", []))
    required_categories = {"HUMAN_APPROVAL", "AUTHORITY_GAP", "EVIDENCE_GAP", "PRODUCTION_TRANSITION", "CONFLICTING_EVIDENCE"}
    if not required_categories.issubset(categories):
        fail("director exception categories incomplete")

    req = set(executive.get("required", []))
    if not {"portfolio", "autonomy", "director_queue"}.issubset(req):
        fail("executive snapshot missing required sections")

    print("LOM CONTROL PLANE CONTRACT: PASS")


if __name__ == "__main__":
    main()
