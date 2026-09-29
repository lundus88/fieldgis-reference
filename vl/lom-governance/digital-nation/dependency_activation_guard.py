"""Post-merge dependency evidence validator for Digital Nation.

This does not mutate GitHub or the binding manifest. It verifies that evidence
is sufficient before a human/operator may update a dependency binding.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


REQUIRED_CHECKS = {
    "LOM Economic Participation P0",
    "VL Governance CI",
    "LOM Master Compliance",
    "LOM Level 6 Exact-Main Regression",
}


def validate_dependency_evidence(evidence: Mapping[str, Any]) -> Dict[str, Any]:
    errors = []

    if evidence.get("pr_number") != 425:
        errors.append("UNEXPECTED_PR")
    if evidence.get("merged") is not True:
        errors.append("PR_NOT_MERGED")
    if not evidence.get("merge_commit_sha"):
        errors.append("MISSING_MERGE_COMMIT_SHA")
    if evidence.get("verified_ref") != "main":
        errors.append("NOT_VERIFIED_ON_MAIN")
    if evidence.get("exact_main") is not True:
        errors.append("EXACT_MAIN_NOT_PROVEN")

    checks = {
        str(x.get("name")): str(x.get("conclusion"))
        for x in evidence.get("checks", [])
    }
    for required in REQUIRED_CHECKS:
        if checks.get(required) != "success":
            errors.append(f"CHECK_NOT_SUCCESS:{required}")

    return {
        "schema": "lom.digital-nation.dependency-activation-evidence/1",
        "decision": "ELIGIBLE_FOR_BOUND_PREVIEW_UPDATE" if not errors else "HOLD",
        "errors": errors,
        "production_authority": False,
        "merge_authority": False,
    }
