from pathlib import Path

from human_gate_intelligence import (
    InterventionEvent,
    build_friction_improvement_backlog,
    classify_gate,
    load_authority_matrix,
    measure_intervention_friction,
    validate_authority_matrix,
)

HERE = Path(__file__).resolve().parent
VL = HERE.parent
NOW = 2_000_000_000


def matrix():
    return load_authority_matrix(VL / "lom-control-plane" / "authority-matrix.json")


def event(event_id="e1", **overrides):
    data = dict(
        event_id=event_id,
        action="RESEARCH",
        environment="NON_PRODUCTION",
        human_intervention=False,
        evidence_complete=True,
        outcome="SUCCESS",
        source_reference=f"event:{event_id}",
        observed_at_epoch=NOW - 10,
    )
    data.update(overrides)
    return InterventionEvent(**data)


def test_canonical_authority_matrix_is_valid():
    result = validate_authority_matrix(matrix())
    assert result["status"] == "READY"
    assert "PRODUCTION_DEPLOY" in result["hard_human_actions"]


def test_protected_main_and_production_are_mandatory_human():
    merge = classify_gate(matrix(), "MERGE_PROTECTED_MAIN", "NON_PRODUCTION")
    deploy = classify_gate(matrix(), "PRODUCTION_DEPLOY", "PRODUCTION")
    assert merge["mandatory_human"] is True
    assert deploy["mandatory_human"] is True
    assert merge["automation_eligible"] is False
    assert deploy["automation_eligible"] is False


def test_nonproduction_research_and_qa_are_automation_eligible():
    research = classify_gate(matrix(), "RESEARCH", "NON_PRODUCTION")
    qa = classify_gate(matrix(), "QA_TEST", "NON_PRODUCTION")
    assert research["automation_eligible"] is True
    assert qa["automation_eligible"] is True


def test_measurement_separates_mandatory_gate_from_avoidable_friction():
    result = measure_intervention_friction(
        matrix(),
        [
            event("auto-clean"),
            event("auto-manual", human_intervention=True),
            event(
                "merge-human",
                action="MERGE_PROTECTED_MAIN",
                human_intervention=True,
            ),
        ],
        now_epoch=NOW,
        max_age_seconds=300,
        target_avoidable_human_rate_pct=60.0,
    )
    assert result["status"] == "HEALTHY"
    assert result["metrics"]["mandatory_human_event_count"] == 1
    assert result["metrics"]["automation_eligible_event_count"] == 2
    assert result["metrics"]["avoidable_human_intervention_count"] == 1
    assert result["metrics"]["avoidable_human_intervention_rate_pct"] == 50.0
    assert len(result["friction_candidates"]) == 1
    assert result["friction_candidates"][0]["action"] == "RESEARCH"


def test_under_five_percent_target_is_measured_only_on_eligible_events():
    events = [event(f"a{i}") for i in range(20)]
    events[0] = event("manual", human_intervention=True)
    events.append(event(
        "mandatory",
        action="FINANCIAL_OR_CONTRACTUAL_COMMITMENT",
        environment="NON_PRODUCTION",
        human_intervention=True,
    ))
    result = measure_intervention_friction(
        matrix(),
        events,
        now_epoch=NOW,
        max_age_seconds=300,
        target_avoidable_human_rate_pct=5.0,
    )
    assert result["status"] == "HEALTHY"
    assert result["metrics"]["avoidable_human_intervention_rate_pct"] == 5.0
    assert result["metrics"]["mandatory_human_event_count"] == 1


def test_above_target_degrades_without_changing_authority():
    result = measure_intervention_friction(
        matrix(),
        [
            event("a", human_intervention=True),
            event("b"),
        ],
        now_epoch=NOW,
        max_age_seconds=300,
        target_avoidable_human_rate_pct=5.0,
    )
    assert result["status"] == "DEGRADED"
    assert result["authority_change"] == "DISABLED"
    assert result["automatic_gate_removal"] == "FORBIDDEN"


def test_missing_mandatory_human_observation_holds():
    result = measure_intervention_friction(
        matrix(),
        [event(
            "deploy-no-human",
            action="PRODUCTION_DEPLOY",
            environment="PRODUCTION",
            human_intervention=False,
        )],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert result["status"] == "HOLD"
    assert any(item["reason"] == "MANDATORY_HUMAN_GATE_NOT_OBSERVED" for item in result["violations"])


def test_unknown_action_holds():
    result = measure_intervention_friction(
        matrix(),
        [event("unknown", action="MAGIC_ACTION")],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert result["status"] == "HOLD"
    assert any(item["reason"] == "UNKNOWN_OR_AMBIGUOUS_AUTHORITY" for item in result["violations"])


def test_stale_event_holds():
    result = measure_intervention_friction(
        matrix(),
        [event("stale", observed_at_epoch=NOW - 1000)],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert result["status"] == "HOLD"


def test_friction_backlog_never_contains_mandatory_gate():
    measurement = measure_intervention_friction(
        matrix(),
        [
            event("manual-research", human_intervention=True),
            event(
                "merge-human",
                action="MERGE_PROTECTED_MAIN",
                human_intervention=True,
            ),
        ],
        now_epoch=NOW,
        max_age_seconds=300,
        target_avoidable_human_rate_pct=100.0,
    )
    backlog = build_friction_improvement_backlog(measurement)
    assert backlog["status"] == "READY"
    assert [item["action"] for item in backlog["items"]] == ["RESEARCH"]
    assert backlog["authority_change"] == "DISABLED"


def test_weakened_authority_matrix_fails_closed():
    broken = matrix()
    for rule in broken["rules"]:
        if rule["action"] == "PRODUCTION_DEPLOY":
            rule["authority"] = "AUTO"
    result = validate_authority_matrix(broken)
    assert result["status"] == "HOLD"
    assert result["reason"] == "HARD_HUMAN_GATE_WEAKENED"


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} Human Gate Minimization Intelligence tests")
