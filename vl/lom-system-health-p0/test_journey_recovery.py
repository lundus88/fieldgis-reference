import json
from pathlib import Path

from journey_registry import load_json, validate_registry, journey_index
from recovery_bridge import RecoveryCandidate, build_recovery_plan, plans_from_assessment

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHA = "a" * 40


def test_golden_journey_registry_covers_canonical_projects():
    journeys = load_json(HERE / "golden_journeys.json")
    sources = load_json(ROOT / "lom-portfolio-runtime" / "source-registry.json")
    result = validate_registry(journeys, sources)
    assert result["status"] == "READY"
    assert result["project_count"] == 7
    assert result["journey_count"] >= result["project_count"]
    index = journey_index(journeys)
    assert set(index) == {item["project_id"] for item in sources["sources"]}


def test_registry_fails_closed_when_project_missing():
    journeys = load_json(HERE / "golden_journeys.json")
    sources = load_json(ROOT / "lom-portfolio-runtime" / "source-registry.json")
    journeys["journeys"] = [item for item in journeys["journeys"] if item["project_id"] != "slp"]
    result = validate_registry(journeys, sources)
    assert result["status"] == "HOLD"
    assert any("PROJECT_WITHOUT_GOLDEN_JOURNEY:slp" in item for item in result["errors"])


def test_safe_preview_drift_stops_at_prepare_pr():
    plan = build_recovery_plan(RecoveryCandidate(
        project_id="vl",
        reason="PREVIEW_DRIFT",
        evidence_sha=SHA,
        source_reference="vercel:deployment:1",
        evidence_fresh=True,
    ))
    assert plan["status"] == "PREPARE_PR"
    assert plan["production_authority"] == "HUMAN_ONLY"
    assert plan["external_action_execution"] == "DISABLED"


def test_production_drift_requires_human_review():
    plan = build_recovery_plan(RecoveryCandidate(
        project_id="vl",
        reason="PRODUCTION_DRIFT",
        evidence_sha=SHA,
        source_reference="vercel:production:1",
        evidence_fresh=True,
    ))
    assert plan["status"] == "HUMAN_REVIEW"
    assert plan["target_action"] == "HUMAN_DECISION_PACKAGE"


def test_database_drift_holds_without_auto_fix():
    plan = build_recovery_plan(RecoveryCandidate(
        project_id="ebkl",
        reason="DATABASE_DRIFT",
        evidence_sha=SHA,
        source_reference="db:fingerprint:1",
        evidence_fresh=True,
    ))
    assert plan["status"] == "HOLD"
    assert plan["external_action_execution"] == "DISABLED"


def test_critical_journey_failure_never_auto_remediates():
    plan = build_recovery_plan(RecoveryCandidate(
        project_id="sabahlot",
        reason="CRITICAL_JOURNEY_FAILED",
        evidence_sha=SHA,
        source_reference="ci:golden:1",
        evidence_fresh=True,
    ))
    assert plan["status"] == "HUMAN_REVIEW"


def test_unknown_recovery_reason_fails_closed():
    plan = build_recovery_plan(RecoveryCandidate(
        project_id="vl",
        reason="MAGIC_FIX",
        evidence_sha=SHA,
        source_reference="evidence:1",
        evidence_fresh=True,
    ))
    assert plan["status"] == "HOLD"
    assert plan["reason"] == "UNREGISTERED_RECOVERY_REASON"


def test_stale_evidence_cannot_prepare_recovery():
    plan = build_recovery_plan(RecoveryCandidate(
        project_id="vl",
        reason="PREVIEW_DRIFT",
        evidence_sha=SHA,
        source_reference="vercel:1",
        evidence_fresh=False,
    ))
    assert plan["status"] == "HOLD"


def test_assessment_reason_set_builds_prioritized_bounded_plans():
    plans = plans_from_assessment(
        project_id="lunduslead",
        reasons=["PREVIEW_DRIFT", "PRODUCTION_DRIFT", "DATABASE_DRIFT"],
        evidence_sha=SHA,
        source_reference="snapshot:1",
        evidence_fresh=True,
    )
    assert [item["status"] for item in plans] == ["HOLD", "HUMAN_REVIEW", "PREPARE_PR"]


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} Golden Journey + Recovery Bridge tests")
