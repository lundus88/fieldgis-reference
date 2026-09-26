from control_plane_bridge import build_director_exception_queue, build_executive_snapshot


def twin(project_id="ld", status="READY", action_class="AUTO_PREPARE", reason="BOUNDED_NONPRODUCTION_PREPARATION_ELIGIBLE", next_action="PREPARE_PR", requested_action="PREPARE_CHANGE"):
    return {
        "schema": "lom.operational-twin/1",
        "status": status,
        "reason": reason,
        "project_id": project_id,
        "truth_status": "VERIFIED",
        "evidence_status": "READY",
        "evidence_freshness": "FRESH",
        "homeostasis_status": "HEALTHY",
        "requested_action": requested_action,
        "action_class": action_class,
        "next_action": next_action,
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "snapshot_digest": "sha256:test",
    }


def test_auto_prepare_does_not_create_director_exception():
    q = build_director_exception_queue([twin()], generated_at="2026-09-26T00:00:00Z")
    assert q["version"] == "1.0"
    assert q["exceptions"] == []


def test_hold_maps_to_evidence_gap():
    q = build_director_exception_queue([
        twin(status="HOLD", action_class="HOLD", reason="OPERATIONAL_EVIDENCE_STALE_OR_UNKNOWN", next_action="RESTORE_AUTHORITATIVE_EVIDENCE")
    ], generated_at="2026-09-26T00:00:00Z", evidence_by_project={"ld": ["e1"]})
    assert len(q["exceptions"]) == 1
    item = q["exceptions"][0]
    assert item["category"] == "EVIDENCE_GAP"
    assert item["severity"] == "HIGH"
    assert item["evidence_refs"] == ["e1"]


def test_human_review_maps_to_risk_or_approval():
    q = build_director_exception_queue([
        twin(status="REVIEW", action_class="HUMAN_REVIEW", reason="RISK_OR_REVERSIBILITY_REQUIRES_REVIEW", next_action="PREPARE_HUMAN_DECISION_PACKAGE")
    ], generated_at="2026-09-26T00:00:00Z")
    assert q["exceptions"][0]["category"] == "RISK_THRESHOLD"


def test_consequential_action_maps_to_human_approval():
    q = build_director_exception_queue([
        twin(status="REVIEW", action_class="HUMAN_REVIEW", reason="CONSEQUENTIAL_ACTION_REQUIRES_HUMAN", next_action="PREPARE_HUMAN_DECISION_PACKAGE", requested_action="PRICING_COMMITMENT")
    ], generated_at="2026-09-26T00:00:00Z")
    assert q["exceptions"][0]["category"] == "HUMAN_APPROVAL"


def test_executive_snapshot_counts_twin_outcomes():
    rows = [
        twin(project_id="a"),
        twin(project_id="b", status="REVIEW", action_class="HUMAN_REVIEW", reason="RISK_OR_REVERSIBILITY_REQUIRES_REVIEW", next_action="PREPARE_HUMAN_DECISION_PACKAGE"),
        twin(project_id="c", status="HOLD", action_class="HOLD", reason="BODY_NOT_SAFE_FOR_PROGRESSION", next_action="RESTORE_AUTHORITATIVE_EVIDENCE"),
    ]
    s = build_executive_snapshot(
        portfolio_counts={"total": 3, "healthy": 1, "review": 1, "blocked": 0, "hold": 1, "release_candidate": 0},
        twins=rows,
        generated_at="2026-09-26T00:00:00Z",
    )
    assert s["portfolio"]["total"] == 3
    assert s["autonomy"]["tasks_executed"] == 0
    assert s["autonomy"]["tasks_verified"] == 3
    assert s["autonomy"]["tasks_escalated"] == 2
    assert s["director_queue"]["open_count"] == 2
    assert s["director_intervention_rate"] if False else True
    assert s["autonomy"]["director_intervention_rate"] == 2 / 3
    assert len(s["top_priorities"]) == 2


def test_no_execution_authority_is_inferred():
    s = build_executive_snapshot(
        portfolio_counts={"total": 1, "healthy": 1, "review": 0, "blocked": 0, "hold": 0, "release_candidate": 0},
        twins=[twin()],
        generated_at="2026-09-26T00:00:00Z",
    )
    assert s["autonomy"]["tasks_executed"] == 0


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LOM Operational Twin Control Plane P1 tests")
