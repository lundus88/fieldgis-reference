from remediation_engine import decide, finalize


def base_case(**overrides):
    case = {
        "action": "NON_PRODUCTION_REVERSIBLE_ACTION",
        "environment": "NON_PRODUCTION",
        "reversible": True,
        "risk": "LOW",
        "evidence": ["failure-evidence"],
        "attempts": 0,
        "executor": "EXECUTOR",
        "validator": "VALIDATOR"
    }
    case.update(overrides)
    return case


def test_allows_bounded_low_risk_remediation():
    assert decide(base_case())["decision"] == "REMEDIATE"


def test_human_only_escalates():
    assert decide(base_case(action="PRODUCTION_DEPLOY_OR_RELEASE"))["decision"] == "ESCALATE"


def test_unknown_authority_holds():
    assert decide(base_case(action=None))["reason"] == "UNKNOWN_AUTHORITY"


def test_production_boundary_escalates():
    assert decide(base_case(environment="PRODUCTION"))["decision"] == "ESCALATE"


def test_irreversible_holds():
    assert decide(base_case(reversible=False))["decision"] == "HOLD"


def test_missing_evidence_holds():
    assert decide(base_case(evidence=[]))["reason"] == "EVIDENCE_REQUIRED"


def test_high_risk_escalates():
    assert decide(base_case(risk="HIGH"))["reason"] == "RISK_THRESHOLD_EXCEEDED"


def test_retry_limit_holds():
    assert decide(base_case(attempts=1))["reason"] == "ATTEMPT_LIMIT_REACHED"


def test_self_certification_holds():
    assert decide(base_case(executor="EXECUTOR", validator="EXECUTOR"))["reason"] == "SELF_CERTIFICATION_FORBIDDEN"


def test_recovery_requires_independent_pass():
    assert finalize("SUCCESS", "PASS")["outcome"] == "RECOVERED"
    assert finalize("SUCCESS", "FAIL")["outcome"] == "FAILED_VALIDATION"
    assert finalize("FAIL", "PASS")["outcome"] == "HOLD"
