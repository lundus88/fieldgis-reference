from orchestrator import Objective, orchestrate


def base(**overrides):
    data = dict(
        objective_id="OBJ-001",
        requested_actions=["GENERATE_ARTIFACT"],
        evidence_refs=["evidence://obj-001"],
        delegated_actions=["GENERATE_ARTIFACT"],
        risk="LOW",
        production=False,
        reversible=True,
        executor="EXECUTOR",
        validator="VALIDATOR",
    )
    data.update(overrides)
    return Objective(**data)


def test_validated_success_completes():
    out = orchestrate(base())
    assert out.state == "COMPLETE"
    assert out.learning_record["policy_change"] == "PROPOSE_ONLY"


def test_human_only_escalates():
    out = orchestrate(base(requested_actions=["PRODUCTION_DEPLOYMENT"], delegated_actions=["PRODUCTION_DEPLOYMENT"]))
    assert out.state == "ESCALATE"
    assert out.stage == "RISK_GATE"


def test_outside_delegation_holds():
    out = orchestrate(base(requested_actions=["RUN_TEST"], delegated_actions=[]))
    assert out.state == "HOLD"


def test_missing_evidence_holds():
    out = orchestrate(base(evidence_refs=[]))
    assert out.state == "HOLD"


def test_self_certification_holds():
    out = orchestrate(base(executor="EXECUTOR", validator="EXECUTOR"))
    assert out.state == "HOLD"
    assert "SELF_CERTIFICATION_FORBIDDEN" in out.reasons


def test_low_risk_failure_can_remediate_and_complete():
    out = orchestrate(base(), execution_ok=False, remediation_ok=True, revalidation_ok=True)
    assert out.state == "COMPLETE"
    assert "REMEDIATED_AND_REVALIDATED" in out.reasons


def test_non_reversible_failure_escalates():
    out = orchestrate(base(reversible=False), execution_ok=False)
    assert out.state == "ESCALATE"
    assert "REMEDIATION_NOT_ALLOWED" in out.reasons


def test_high_risk_escalates_before_execution():
    out = orchestrate(base(risk="HIGH"))
    assert out.state == "ESCALATE"


def test_remediation_failure_escalates():
    out = orchestrate(base(), execution_ok=False, remediation_ok=False)
    assert out.state == "ESCALATE"


def test_revalidation_failure_escalates():
    out = orchestrate(base(), validation_ok=False, remediation_ok=True, revalidation_ok=False)
    assert out.state == "ESCALATE"
    assert out.stage == "REVALIDATE"
