import json
from pathlib import Path

from organism import (
    ORGANS,
    SensorySignal,
    build_reflex_plan,
    homeostasis,
    load_registry,
    route_signal,
    validate_body_registry,
)

HERE = Path(__file__).resolve().parent
REGISTRY = load_registry(HERE / "organ-registry.json")
NOW = 2_000_000_000


def signal(**overrides):
    data = dict(
        signal_id="sig-0000000000000001",
        source_organ="eyes",
        project_id="ebkl",
        signal_type="HEALTH",
        severity="LOW",
        observed_at_epoch=NOW - 10,
        expires_at_epoch=NOW + 300,
        evidence_refs=("evidence:1",),
        requested_action=None,
        production=False,
        reversible=True,
        risk="LOW",
    )
    data.update(overrides)
    return SensorySignal(**data)


def test_body_registry_covers_all_organs_and_real_components():
    result = validate_body_registry(REGISTRY)
    assert result["status"] == "READY"
    assert set(result["organs"]) == ORGANS
    assert result["component_count"] >= len(ORGANS)


def test_health_signal_is_monitor_only():
    result = route_signal(signal(), now_epoch=NOW)
    assert result["action_class"] == "MONITOR"
    assert result["execution_authority"] == "NONE"


def test_stale_signal_holds_before_any_action():
    result = route_signal(signal(expires_at_epoch=NOW - 1), now_epoch=NOW)
    assert result["action_class"] == "HOLD"
    assert result["reason"] == "SIGNAL_STALE"


def test_low_risk_reversible_regression_can_only_auto_prepare():
    result = route_signal(signal(
        signal_type="REGRESSION",
        severity="MEDIUM",
        requested_action="NON_PROD_CODE",
    ), now_epoch=NOW)
    assert result["action_class"] == "AUTO_PREPARE"
    plan = build_reflex_plan(result)
    assert plan["status"] == "PREPARE_PR"
    assert plan["external_execution"] == "DISABLED"


def test_production_or_human_only_action_always_routes_human():
    one = route_signal(signal(
        signal_type="WORK_READY",
        requested_action="PRODUCTION_DEPLOY",
        production=True,
    ), now_epoch=NOW)
    two = route_signal(signal(
        signal_type="AUTHORITY_REQUEST",
        requested_action="MERGE_PROTECTED_MAIN",
    ), now_epoch=NOW)
    assert one["action_class"] == "HUMAN_REVIEW"
    assert two["action_class"] == "HUMAN_REVIEW"


def test_security_signal_never_auto_executes():
    result = route_signal(signal(
        source_organ="immune_system",
        signal_type="SECURITY",
        severity="HIGH",
    ), now_epoch=NOW)
    assert result["action_class"] == "HOLD"
    assert "immune_system" in result["route"]


def test_critical_incident_routes_to_human_review():
    result = route_signal(signal(
        signal_type="INCIDENT",
        severity="CRITICAL",
    ), now_epoch=NOW)
    assert result["action_class"] == "HUMAN_REVIEW"
    assert "voice" in result["route"]


def test_evidence_gap_holds_until_truth_is_restored():
    result = route_signal(signal(
        signal_type="EVIDENCE_GAP",
        severity="MEDIUM",
    ), now_epoch=NOW)
    assert result["action_class"] == "HOLD"
    assert result["reason"] == "TRUTH_MUST_BE_RESTORED_BEFORE_ACTION"


def organ_state(name, status="HEALTHY", **overrides):
    row = {
        "organ": name,
        "status": status,
        "observed_at_epoch": NOW - 10,
        "evidence_refs": [f"evidence:{name}"],
    }
    row.update(overrides)
    return row


def test_homeostasis_all_organs_healthy():
    result = homeostasis(
        REGISTRY,
        [organ_state(name) for name in sorted(ORGANS)],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert result["status"] == "HEALTHY"
    assert result["missing_organs"] == []
    assert result["execution_authority"] == "NONE"


def test_homeostasis_missing_organ_fails_closed():
    states = [organ_state(name) for name in sorted(ORGANS) if name != "hands"]
    result = homeostasis(REGISTRY, states, now_epoch=NOW, max_age_seconds=300)
    assert result["status"] == "HOLD"
    assert result["missing_organs"] == ["hands"]


def test_homeostasis_stale_organ_fails_closed():
    states = [organ_state(name) for name in sorted(ORGANS)]
    states[0]["observed_at_epoch"] = NOW - 1000
    result = homeostasis(REGISTRY, states, now_epoch=NOW, max_age_seconds=300)
    assert result["status"] == "HOLD"


def test_failed_immune_system_makes_whole_body_failed():
    states = [organ_state(name) for name in sorted(ORGANS)]
    for row in states:
        if row["organ"] == "immune_system":
            row["status"] = "FAILED"
    result = homeostasis(REGISTRY, states, now_epoch=NOW, max_age_seconds=300)
    assert result["status"] == "FAILED"


def test_integrated_enhancements_match_merged_repo_truth():
    items = REGISTRY["integrated_enhancements"]
    assert {item["pull_request"] for item in items} == {386, 387}
    health = next(item for item in items if item["pull_request"] == 386)
    vps = next(item for item in items if item["pull_request"] == 387)
    assert health["repository_status"] == "MERGED"
    assert health["integration_status"] == "BOUND_TO_EYES"
    assert vps["repository_status"] == "MERGED"
    assert vps["integration_status"] == "BOUND_TO_HANDS_DORMANT"
    assert vps["activation_status"] == "HOLD_LIVE_VPS_UNVERIFIED"
    assert all(item["required_for_p0_body"] is False for item in items)


def test_merged_bridges_are_canonical_organ_components():
    organs = {item["organ"]: item for item in REGISTRY["organs"]}
    assert "vl/lom-system-health-p0/body_probe_adapter.py" in organs["eyes"]["canonical_components"]
    assert "vl/lom-vps-execution-node-p0/body_executor_adapter.py" in organs["hands"]["canonical_components"]


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LOM Organism Integration P0 tests")
