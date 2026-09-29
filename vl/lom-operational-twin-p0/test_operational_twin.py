from operational_twin import build_operational_twin


def truth(status="VERIFIED", reason="EVIDENCE_BOUND_STATE"):
    return {
        "schema": "lom.project-state-truth/1",
        "mode": "READ_ONLY_NON_PRODUCTION",
        "status": status,
        "reason": reason,
    }


def evidence(status="READY", freshness="FRESH", reason="LIVE_EVIDENCE_READY"):
    return {
        "schema": "lom.live-operational-evidence-fabric/1",
        "status": status,
        "freshness": freshness,
        "reason": reason,
    }


def body(status="HEALTHY"):
    return {"schema": "lom.organism-homeostasis/1", "status": status}


def twin(**kwargs):
    defaults = dict(
        project_id="ld",
        project_truth=truth(),
        operational_evidence=evidence(),
        homeostasis=body(),
        requested_action="PREPARE_CHANGE",
        production=False,
        risk="LOW",
        reversible=True,
    )
    defaults.update(kwargs)
    return build_operational_twin(**defaults)


def test_healthy_low_risk_reversible_reaches_prepare_pr_only():
    result = twin()
    assert result["status"] == "READY"
    assert result["action_class"] == "AUTO_PREPARE"
    assert result["next_action"] == "PREPARE_PR"
    assert result["execution_authority"] == "NONE"
    assert result["production_authority"] == "HUMAN_ONLY"


def test_stale_evidence_fails_closed():
    result = twin(operational_evidence=evidence(freshness="STALE"))
    assert result["status"] == "HOLD"
    assert result["reason"] == "OPERATIONAL_EVIDENCE_STALE_OR_UNKNOWN"


def test_missing_truth_schema_fails_closed():
    result = twin(project_truth={"status": "VERIFIED"})
    assert result["status"] == "HOLD"
    assert result["reason"] == "PROJECT_TRUTH_SCHEMA_INVALID"


def test_body_hold_blocks_progression():
    result = twin(homeostasis=body("HOLD"))
    assert result["status"] == "HOLD"
    assert result["reason"] == "BODY_NOT_SAFE_FOR_PROGRESSION"


def test_production_is_human_only():
    result = twin(production=True)
    assert result["status"] == "REVIEW"
    assert result["action_class"] == "HUMAN_REVIEW"
    assert result["next_action"] == "PREPARE_HUMAN_DECISION_PACKAGE"


def test_protected_main_merge_is_human_only():
    result = twin(requested_action="MERGE_PROTECTED_MAIN")
    assert result["action_class"] == "HUMAN_REVIEW"
    assert result["protected_main_merge"] == "HUMAN_ONLY"


def test_medium_risk_requires_review():
    result = twin(risk="MEDIUM")
    assert result["status"] == "REVIEW"
    assert result["action_class"] == "HUMAN_REVIEW"


def test_nonreversible_requires_review():
    result = twin(reversible=False)
    assert result["status"] == "REVIEW"
    assert result["action_class"] == "HUMAN_REVIEW"


def test_digest_is_deterministic():
    a = twin()
    b = twin()
    assert a["snapshot_digest"] == b["snapshot_digest"]


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LOM Operational Twin P0 tests")
