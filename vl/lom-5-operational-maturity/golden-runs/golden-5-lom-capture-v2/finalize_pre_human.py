from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATURITY = HERE.parents[1]
SPEC_DATA = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
EXEC = json.loads((HERE / "execution-result.json").read_text(encoding="utf-8"))
VALIDATION = json.loads((HERE / "independent-validation.json").read_text(encoding="utf-8"))

module_spec = importlib.util.spec_from_file_location("evidence_capture", MATURITY / "evidence_capture.py")
capture = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(capture)

def main() -> int:
    budgets = SPEC_DATA["budgets"]
    envelope = capture.begin_capture(
        run_id=SPEC_DATA["run_id"],
        project_id=SPEC_DATA["project_id"],
        request_id=SPEC_DATA["request_id"],
        app_spec=SPEC_DATA["app_spec"],
        context_policy=SPEC_DATA["context_policy"],
        model_routing_decision=SPEC_DATA["model_routing_decision"],
        capability_scope=SPEC_DATA["capability_scope"],
        resource_scope=SPEC_DATA["resource_scope"],
        token_budget=budgets["token_budget"],
        cost_budget=budgets["cost_budget"],
        time_budget_seconds=budgets["time_budget_seconds"],
        retry_budget=budgets["retry_budget"],
        source_commit_sha=EXEC["github_sha"],
    )

    artifact_bytes = (HERE / "execution-result.json").read_bytes()
    record = capture.finalize_capture(
        envelope,
        artifact_bytes=artifact_bytes,
        qa_security_evidence=[
            {
                "kind": "github-actions",
                "run_id": EXEC["github_run_id"],
                "status": "SUCCESS",
                "source_sha": EXEC["github_sha"],
            },
            {
                "kind": "canonical-compliance",
                "status": "PASS",
                "source_sha": EXEC["github_sha"],
            },
        ],
        independent_validation=VALIDATION,
        remediation_history=[],
        release_candidate_state="RC_AWAITING_HUMAN_REVIEW",
        human_decision=None,
        release_outcome="NO_RELEASE_ACTION",
        rollback_audit_linkage=f"github-run:{EXEC['github_run_id']}",
        final_outcome="PASS",
        attempts=EXEC["attempts"],
        elapsed_seconds=EXEC["elapsed_seconds"],
        estimated_model_tool_cost=EXEC["estimated_model_tool_cost"],
        production_approval=False,
        builder_self_certified=False,
        authority_expansion_incident=False,
        fabricated_pass_incident=False,
        multi_agent_delegation={"demonstrated": False, "authority_expanded": False},
    )

    out = HERE / "pre-human-evidence-record.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2, sort_keys=True))

    if record["evidence_state"] != "PARTIAL":
        raise SystemExit("FAIL: pre-human record must remain PARTIAL")
    if "HUMAN_DECISION_REQUIRED" not in record.get("capture_errors", []):
        raise SystemExit("FAIL: human gate was not enforced")
    if record.get("promotion_allowed") is not False:
        raise SystemExit("FAIL: promotion must remain blocked before human decision")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
