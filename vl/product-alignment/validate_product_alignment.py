#!/usr/bin/env python3
import json, sys
from pathlib import Path

REQUIRED_INTENT = [
    "primary_user","core_problem","desired_outcome","must_have",
    "must_not","success_metric","commercial_model","compliance_constraints",
    "release_scope","human_decision_boundaries"
]


def fail(msg):
    raise ValueError(msg)


def load(path):
    return json.loads(Path(path).read_text())


def validate(doc):
    intent = doc.get("founder_intent") or {}
    reqs = doc.get("user_requirements") or []
    tests = doc.get("acceptance_tests") or []

    missing = [k for k in REQUIRED_INTENT if k not in intent or intent[k] in (None,"",[])]
    if missing:
        fail("missing Founder Intent fields: " + ", ".join(missing))

    if not reqs:
        fail("at least one user requirement is required")
    if not tests:
        fail("at least one acceptance test is required")

    req_ids=set()
    intent_refs=set(intent.get("intent_ids") or [])
    for r in reqs:
        rid=r.get("id")
        if not rid or rid in req_ids:
            fail("requirements must have unique non-empty ids")
        req_ids.add(rid)
        for key in ("user","context","expected_outcome","priority","intent_refs"):
            if key not in r or r[key] in (None,"",[]):
                fail(f"requirement {rid} missing {key}")
        if r.get("priority") == "P0" and not r.get("acceptance_test_ids"):
            fail(f"P0 requirement {rid} has no acceptance test mapping")
        if intent_refs and any(ref not in intent_refs for ref in r.get("intent_refs",[])):
            fail(f"requirement {rid} references unknown Founder Intent id")

    test_ids=set()
    mapped_reqs=set()
    for t in tests:
        tid=t.get("id")
        if not tid or tid in test_ids:
            fail("acceptance tests must have unique non-empty ids")
        test_ids.add(tid)
        for key in ("requirement_ids","observable_pass_condition"):
            if key not in t or t[key] in (None,"",[]):
                fail(f"acceptance test {tid} missing {key}")
        unknown=[rid for rid in t.get("requirement_ids",[]) if rid not in req_ids]
        if unknown:
            fail(f"acceptance test {tid} references unknown requirement: {unknown}")
        mapped_reqs.update(t.get("requirement_ids",[]))

    for r in reqs:
        if r.get("priority") == "P0":
            declared=set(r.get("acceptance_test_ids",[]))
            unknown=declared-test_ids
            if unknown:
                fail(f"P0 requirement {r['id']} references unknown tests: {sorted(unknown)}")
            actual={t["id"] for t in tests if r["id"] in t.get("requirement_ids",[])}
            if not declared.issubset(actual):
                fail(f"P0 requirement {r['id']} mapping is not bidirectionally traceable")
            if r["id"] not in mapped_reqs:
                fail(f"P0 requirement {r['id']} is not covered by acceptance tests")

    contradictions=doc.get("contradictions") or []
    unresolved=[c for c in contradictions if c.get("status") != "resolved"]
    if unresolved:
        fail("unresolved contradictory requirements present")

    manifest=doc.get("traceability_manifest") or {}
    if manifest.get("founder_intent_hash") and not manifest.get("certification_input_hash"):
        fail("traceability manifest missing certification_input_hash")

    return True


def main():
    if len(sys.argv) != 2:
        print("usage: validate_product_alignment.py <document.json>", file=sys.stderr)
        return 2
    try:
        validate(load(sys.argv[1]))
    except Exception as e:
        print(f"PRODUCT ALIGNMENT: FAIL - {e}")
        return 1
    print("PRODUCT ALIGNMENT: PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
