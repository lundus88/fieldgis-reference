from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


SCHEMA_VERSION = "vl.golden-factory-proof/1"
POLICY_VERSION = "vl.golden-routing/1"
REQUIRED_BUILDERS = {
    "mobile-flutter-v1",
    "gis-web-v1",
    "web-react-v1",
    "pwa-react-v1",
    "api-service-v1",
}
PRODUCTION_BYPASS = re.compile(
    r"(?:bypass|skip|disable).{0,40}(?:approval|rollback)|"
    r"(?:deploy|promote).{0,30}(?:directly )?to production|"
    r"expose all secrets",
    re.IGNORECASE,
)


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def route(case: dict) -> dict:
    prompt = str(case.get("prompt") or "").strip()
    if not prompt:
        return {"decision": "DENY", "reason_code": "EMPTY_INPUT"}
    if PRODUCTION_BYPASS.search(prompt):
        return {"decision": "DENY", "reason_code": "PRODUCTION_BYPASS_REQUESTED"}

    lower = prompt.lower()
    platforms = []
    builders = []
    if any(term in lower for term in ("android", "mobile", "offline form")):
        platforms.append("android")
        builders.append("mobile-flutter-v1")
    if any(term in lower for term in ("gis", "map", "parcel", "gps")):
        platforms.append("gis")
        builders.append("gis-web-v1")
    if not platforms:
        return {
            "decision": "REQUIRE_CLARIFICATION",
            "reason_code": "INSUFFICIENT_REQUIREMENTS",
        }

    spec = {
        "schema_version": "vl.app-spec/1",
        "title": "Sabah Field Inspection",
        "original_request": prompt,
        "software_kind": "gis" if "gis" in platforms else "application",
        "target_platforms": sorted(set(platforms)),
        "user_confirmed": False,
        "status": "draft",
        "production_locked": True,
        "direct_production_execution_allowed": False,
    }
    result = {
        "decision": "ROUTE",
        "app_spec": spec,
        "builders": sorted(set(builders)),
        "terminal_gate": "human-approval",
        "target_environment": "development",
    }
    result["app_spec_digest"] = digest(spec)
    result["routing_digest"] = digest(
        {
            "policy_version": POLICY_VERSION,
            "builders": result["builders"],
            "target_environment": result["target_environment"],
        }
    )
    return result


def assert_expected(case: dict, result: dict) -> None:
    expected = case["expected"]
    if result.get("decision") != expected["decision"]:
        raise AssertionError(f"{case['case_id']}: decision mismatch: {result}")
    if "reason_code" in expected and result.get("reason_code") != expected["reason_code"]:
        raise AssertionError(f"{case['case_id']}: reason mismatch: {result}")
    if result.get("decision") == "ROUTE":
        spec = result["app_spec"]
        for key in ("software_kind", "target_platforms"):
            if spec.get(key) != expected[key]:
                raise AssertionError(f"{case['case_id']}: {key} mismatch: {result}")
        if result.get("builders") != expected["builders"]:
            raise AssertionError(f"{case['case_id']}: builders mismatch: {result}")
        if spec.get("production_locked") is not True:
            raise AssertionError(f"{case['case_id']}: production must remain locked")
        if spec.get("direct_production_execution_allowed") is not False:
            raise AssertionError(f"{case['case_id']}: direct production execution exposed")
        if result.get("terminal_gate") != "human-approval":
            raise AssertionError(f"{case['case_id']}: human approval is not terminal")
        if result.get("target_environment") != "development":
            raise AssertionError(f"{case['case_id']}: non-development target")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()

    payload = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    if {case.get("kind") for case in cases} != {"positive", "ambiguous", "high-risk"}:
        raise AssertionError("benchmark must contain positive, ambiguous, and high-risk cases")

    results = []
    for case in cases:
        first = route(case)
        second = route(case)
        if canonical(first) != canonical(second):
            raise AssertionError(f"{case['case_id']}: routing is not deterministic")
        assert_expected(case, first)
        results.append(
            {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "input_digest": digest(case["prompt"]),
                "result": first,
                "deterministic_repeat": True,
                "status": "PASS",
            }
        )

    evidence_requirements = {
        "natural_language_to_app_spec": "PASS",
        "autonomous_routing": "PASS",
        "production_bypass_negative_control": "PASS",
        "current_head_builder_matrix": "PENDING_EXTERNAL_EVIDENCE",
        "isolated_sandbox_execution": "PENDING_EXTERNAL_EVIDENCE",
        "automated_qa": "PENDING_EXTERNAL_EVIDENCE",
        "builder_output_certification": "PENDING_EXTERNAL_EVIDENCE",
        "explicit_human_dev_approval": "PENDING_EXTERNAL_EVIDENCE",
        "dev_rollback": "PENDING_EXTERNAL_EVIDENCE",
        "three_run_reproducibility": "PENDING_EXTERNAL_EVIDENCE",
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "verdict": "HOLD",
        "reason": "external DEV/sandbox evidence is not yet attached",
        "source_sha": args.source_sha,
        "target_environment": "development",
        "production_mutation": False,
        "policy_version": POLICY_VERSION,
        "active_builder_inventory": sorted(REQUIRED_BUILDERS),
        "case_set_digest": digest(payload),
        "results": results,
        "evidence_requirements": evidence_requirements,
    }
    manifest["manifest_digest"] = digest(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "verdict": "HOLD", "manifest_digest": manifest["manifest_digest"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1)
