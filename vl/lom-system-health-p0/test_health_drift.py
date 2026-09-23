import json
import os
import tempfile

from health_drift import (
    CrossSystemEvidenceLedger,
    ProjectObservation,
    RegressionResult,
    assess_project_health,
    build_portfolio_snapshot,
    detect_deployment_drift,
    evaluate_regression_sentinel,
)

NOW = 2_000_000_000
MAIN = "a" * 40
OLD = "b" * 40
DB = "db-schema-v1"


def observation(**overrides):
    base = dict(
        project_id="lunduslead",
        repository="lundus88/lundus-lead",
        main_sha=MAIN,
        observed_at_epoch=NOW - 30,
        max_age_seconds=300,
        ci_sha=MAIN,
        ci_status="PASS",
        runtime_status="HEALTHY",
        evidence_refs=("github:check:1", "runtime:health:1"),
        preview_sha=MAIN,
        production_sha=OLD,
        preview_required=True,
        production_policy="LOCKED",
        database_fingerprint=DB,
        expected_database_fingerprint=DB,
    )
    base.update(overrides)
    return ProjectObservation(**base)


def regression(journey_id="lead-golden", **overrides):
    base = dict(
        project_id="lunduslead",
        journey_id=journey_id,
        critical=True,
        status="PASS",
        exact_sha=MAIN,
        evidence_ref=f"check:{journey_id}",
        observed_at_epoch=NOW - 20,
    )
    base.update(overrides)
    return RegressionResult(**base)


def test_locked_production_drift_is_visible_but_not_auto_release_pressure():
    result = assess_project_health(observation(), now_epoch=NOW)
    assert result["status"] == "DEGRADED"
    assert "EXPECTED_PRODUCTION_HOLD_DRIFT" in result["reasons"]
    assert result["production_authority"] == "HUMAN_ONLY"
    assert result["deployment"]["deployment_mutation"] == "DISABLED"


def test_tracking_production_drift_requires_action():
    result = assess_project_health(
        observation(production_policy="TRACK_MAIN", production_sha=OLD),
        now_epoch=NOW,
    )
    assert result["status"] == "ACTION_REQUIRED"
    assert "PRODUCTION_DRIFT" in result["reasons"]


def test_preview_drift_is_degraded_not_silently_healthy():
    result = assess_project_health(
        observation(preview_sha=OLD, production_sha=MAIN),
        now_epoch=NOW,
    )
    assert result["status"] == "DEGRADED"
    assert "PREVIEW_DRIFT" in result["reasons"]


def test_ci_must_be_exact_main():
    result = assess_project_health(
        observation(ci_sha=OLD, production_sha=MAIN),
        now_epoch=NOW,
    )
    assert result["status"] == "HOLD"
    assert "CI_NOT_EXACT_MAIN" in result["reasons"]


def test_ci_or_runtime_failure_requires_action():
    ci = assess_project_health(
        observation(ci_status="FAIL", production_sha=MAIN),
        now_epoch=NOW,
    )
    runtime = assess_project_health(
        observation(runtime_status="FAILED", production_sha=MAIN),
        now_epoch=NOW,
    )
    assert ci["status"] == "ACTION_REQUIRED" and "CI_FAILURE" in ci["reasons"]
    assert runtime["status"] == "ACTION_REQUIRED" and "RUNTIME_FAILURE" in runtime["reasons"]


def test_stale_observation_fails_closed():
    result = assess_project_health(
        observation(observed_at_epoch=NOW - 1000),
        now_epoch=NOW,
    )
    assert result["status"] == "HOLD"
    assert result["reasons"] == ["OBSERVATION_STALE"]


def test_database_drift_holds():
    result = assess_project_health(
        observation(database_fingerprint="unexpected", production_sha=MAIN),
        now_epoch=NOW,
    )
    assert result["status"] == "HOLD"
    assert "DATABASE_DRIFT" in result["reasons"]


def test_regression_sentinel_all_required_pass():
    result = evaluate_regression_sentinel(
        project_id="lunduslead",
        expected_main_sha=MAIN,
        required_journeys={"lead-golden", "tender-watch"},
        results=[regression(), regression("tender-watch")],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert result["status"] == "HEALTHY"
    assert result["missing_journeys"] == []


def test_regression_sentinel_missing_or_wrong_sha_holds():
    missing = evaluate_regression_sentinel(
        project_id="lunduslead",
        expected_main_sha=MAIN,
        required_journeys={"lead-golden", "tender-watch"},
        results=[regression()],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    wrong = evaluate_regression_sentinel(
        project_id="lunduslead",
        expected_main_sha=MAIN,
        required_journeys={"lead-golden"},
        results=[regression(exact_sha=OLD)],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert missing["status"] == "HOLD"
    assert "REQUIRED_JOURNEY_MISSING" in missing["reasons"]
    assert wrong["status"] == "HOLD"
    assert "REGRESSION_NOT_EXACT_MAIN" in wrong["reasons"]


def test_critical_regression_failure_requires_action():
    result = evaluate_regression_sentinel(
        project_id="lunduslead",
        expected_main_sha=MAIN,
        required_journeys={"lead-golden"},
        results=[regression(status="FAIL")],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert result["status"] == "ACTION_REQUIRED"
    assert "CRITICAL_JOURNEY_FAILED" in result["reasons"]


def test_noncritical_failure_degrades_only():
    result = evaluate_regression_sentinel(
        project_id="lunduslead",
        expected_main_sha=MAIN,
        required_journeys={"report-polish"},
        results=[regression("report-polish", critical=False, status="FAIL")],
        now_epoch=NOW,
        max_age_seconds=300,
    )
    assert result["status"] == "DEGRADED"


def test_cross_system_evidence_ledger_survives_reopen_and_detects_tamper():
    fd, path = tempfile.mkstemp(prefix="lom-health-", suffix=".jsonl")
    os.close(fd)
    try:
        os.remove(path)
        ledger = CrossSystemEvidenceLedger(path)
        first = ledger.append(
            record_type="PROJECT_HEALTH",
            project_id="lunduslead",
            payload={"status": "DEGRADED"},
            evidence_refs=["github:1"],
            observed_at_epoch=NOW,
        )
        second = ledger.append(
            record_type="REGRESSION_SENTINEL",
            project_id="lunduslead",
            payload={"status": "HEALTHY"},
            evidence_refs=["check:1"],
            observed_at_epoch=NOW + 1,
        )
        reopened = CrossSystemEvidenceLedger(path)
        verified = reopened.verify()
        assert verified["status"] == "READY"
        assert verified["record_count"] == 2
        assert verified["head_hash"] == second["record_hash"]
        assert first["prev_hash"] == "GENESIS"

        lines = open(path, encoding="utf-8").read().splitlines()
        tampered = json.loads(lines[0])
        tampered["project_id"] = "tampered"
        lines[0] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
        open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        assert CrossSystemEvidenceLedger(path).verify()["status"] == "HOLD"
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def test_portfolio_uses_worst_verified_state_and_keeps_authority_boundary():
    health = [
        assess_project_health(observation(production_sha=MAIN), now_epoch=NOW),
        assess_project_health(
            observation(
                project_id="ebkl",
                repository="lundus88/ebkl",
                runtime_status="DEGRADED",
                production_sha=MAIN,
            ),
            now_epoch=NOW,
        ),
    ]
    sentinels = [
        evaluate_regression_sentinel(
            project_id="lunduslead",
            expected_main_sha=MAIN,
            required_journeys={"lead-golden"},
            results=[regression()],
            now_epoch=NOW,
            max_age_seconds=300,
        ),
        evaluate_regression_sentinel(
            project_id="ebkl",
            expected_main_sha=MAIN,
            required_journeys={"fieldbook"},
            results=[
                RegressionResult(
                    "ebkl", "fieldbook", True, "PASS", MAIN, "check:fieldbook", NOW - 10
                )
            ],
            now_epoch=NOW,
            max_age_seconds=300,
        ),
    ]
    snapshot = build_portfolio_snapshot(health, sentinels)
    assert snapshot["overall"] == "DEGRADED"
    assert snapshot["autonomous_ceiling"] == "PREPARE_PR"
    assert snapshot["production_authority"] == "HUMAN_ONLY"
    assert snapshot["protected_main_merge"] == "HUMAN_ONLY"
    assert snapshot["execution_authority"] == "NONE"


def test_unknown_production_policy_holds():
    drift = detect_deployment_drift(observation(production_policy="MAGIC"))
    assert drift["status"] == "HOLD"
    assert drift["production_authority"] == "HUMAN_ONLY"


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LOM System Health & Drift P0 tests")
