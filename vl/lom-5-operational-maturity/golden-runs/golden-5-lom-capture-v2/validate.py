from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXEC = json.loads((HERE / "execution-result.json").read_text(encoding="utf-8"))
OUT = HERE / "independent-validation.json"

def main() -> int:
    errors = []
    if EXEC.get("schema") != "lom.golden-workflow-execution/2":
        errors.append("INVALID_EXECUTION_SCHEMA")
    if EXEC.get("execution_passed") is not True:
        errors.append("EXECUTION_NOT_PASS")
    if EXEC.get("production_locked") is not True:
        errors.append("PRODUCTION_LOCK_REQUIRED")
    if EXEC.get("autonomous_ceiling") != "PREPARE_PR":
        errors.append("AUTHORITY_CEILING_DRIFT")
    if EXEC.get("model_or_external_api_calls") != 0:
        errors.append("UNEXPECTED_EXTERNAL_CALL")
    if EXEC.get("estimated_model_tool_cost") != 0.0:
        errors.append("UNEXPECTED_MODEL_TOOL_COST")
    for key in (
        "budget_overrun",
        "authority_expansion_incident",
        "fabricated_pass_incident",
        "production_approval",
        "builder_self_certified",
    ):
        if EXEC.get(key) is not False:
            errors.append(f"INVALID_{key.upper()}")

    checks = EXEC.get("checks")
    if not isinstance(checks, list) or len(checks) < 2:
        errors.append("CHECK_SET_INCOMPLETE")
    elif any(c.get("returncode") != 0 for c in checks):
        errors.append("CHECK_FAILURE_PRESENT")

    result = {
        "schema": "lom.independent-validation/2",
        "validator_role": "INDEPENDENT_VALIDATOR",
        "status": "PASS" if not errors else "HOLD",
        "errors": sorted(errors),
        "source_github_sha": EXEC.get("github_sha"),
        "source_github_run_id": EXEC.get("github_run_id"),
        "builder_self_certification": False,
        "production_authority": "HUMAN_ONLY",
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
