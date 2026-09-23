from body_probe_adapter import portfolio_snapshot_to_organ_probe
from health_drift import (
    ProjectObservation,
    RegressionResult,
    assess_project_health,
    build_portfolio_snapshot,
    evaluate_regression_sentinel,
)

NOW = 2_000_000_000
MAIN = "a" * 40


def observation(**overrides):
    data = dict(
        project_id="ebkl",
        repository="lundus88/ebkl",
        main_sha=MAIN,
        observed_at_epoch=NOW - 20,
        max_age_seconds=300,
        ci_sha=MAIN,
        ci_status="PASS",
        runtime_status="HEALTHY",
        evidence_refs=("github:ci", "runtime:health"),
        preview_sha=MAIN,
        production_sha=MAIN,
        preview_required=True,
        production_policy="TRACK_MAIN",
    )
    data.update(overrides)
    return ProjectObservation(**data)


def sentinel(status="PASS"):
    return evaluate_regression_sentinel(
        project_id="ebkl",
        expected_main_sha=MAIN,
        required_journeys={"fieldbook"},
        results=[
            RegressionResult(
                "ebkl",
                "fieldbook",
                True,
                status,
                MAIN,
                "check:fieldbook",
                NOW - 10,
            )
        ],
        now_epoch=NOW,
        max_age_seconds=300,
    )


def snapshot(**observation_overrides):
    health = assess_project_health(observation(**observation_overrides), now_epoch=NOW)
    return build_portfolio_snapshot([health], [sentinel()], expected_project_ids={"ebkl"})


def test_portfolio_snapshot_exposes_conservative_freshness():
    item = snapshot()
    assert item["observed_at_epoch"] == NOW - 20
    assert item["fresh_until_epoch"] == NOW + 280


def test_healthy_portfolio_becomes_current_eyes_probe():
    probe = portfolio_snapshot_to_organ_probe(snapshot(), now_epoch=NOW)
    assert probe["organ"] == "eyes"
    assert probe["status"] == "HEALTHY"
    assert probe["observed_at_epoch"] == NOW - 20
    assert probe["evidence_refs"][0].startswith("portfolio-health:")
    assert probe["execution_authority"] == "NONE"


def test_action_required_never_becomes_healthy_body_evidence():
    bad = assess_project_health(observation(ci_status="FAIL"), now_epoch=NOW)
    item = build_portfolio_snapshot([bad], [sentinel()], expected_project_ids={"ebkl"})
    probe = portfolio_snapshot_to_organ_probe(item, now_epoch=NOW)
    assert item["overall"] == "ACTION_REQUIRED"
    assert probe["status"] == "HOLD"
    assert probe["reason"] == "PORTFOLIO_ACTION_REQUIRED"


def test_stale_snapshot_fails_closed():
    item = snapshot()
    probe = portfolio_snapshot_to_organ_probe(item, now_epoch=item["fresh_until_epoch"] + 1)
    assert probe["status"] == "HOLD"
    assert probe["reason"] == "PORTFOLIO_HEALTH_STALE"


def test_unknown_schema_fails_closed():
    probe = portfolio_snapshot_to_organ_probe({"schema": "magic"}, now_epoch=NOW)
    assert probe["status"] == "HOLD"
    assert probe["reason"] == "PORTFOLIO_HEALTH_SCHEMA_INVALID"


def test_health_adapter_cannot_impersonate_other_organs():
    probe = portfolio_snapshot_to_organ_probe(snapshot(), now_epoch=NOW, organ="hands")
    assert probe["status"] == "HOLD"
    assert probe["reason"] == "HEALTH_ADAPTER_ORGAN_FORBIDDEN"


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} LOM System Health body-probe adapter tests")
