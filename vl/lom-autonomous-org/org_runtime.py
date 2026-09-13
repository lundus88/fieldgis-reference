HUMAN_ONLY = {
    "PRODUCTION_RELEASE","PROTECTED_MAIN_MERGE","PRODUCTION_DATA_MUTATION",
    "AUTHORITY_WIDENING","CUSTOMER_COMMITMENT","BID_SUBMISSION",
    "PRICING_COMMITMENT","CONTRACT_COMMITMENT","FINANCIAL_COMMITMENT"
}

DELEGATED_ACTIONS = {
    "READ_ONLY_OBSERVATION",
    "GENERATE_ARTIFACT",
    "RUN_TEST",
    "RENDER_REPORT",
    "NON_PRODUCTION_REVERSIBLE_ACTION"
}


def route(action: str, evidence_status: str, risk: str, reversible: bool, production: bool) -> dict:
    if not action:
        raise ValueError("action required")
    if action in HUMAN_ONLY:
        return {"decision":"ESCALATE","reason":"HUMAN_ONLY_ACTION"}
    if action not in DELEGATED_ACTIONS:
        return {"decision":"HOLD","reason":"UNKNOWN_OR_UNDELEGATED_AUTHORITY"}
    if evidence_status in {"MISSING","CONTRADICTORY"}:
        return {"decision":"HOLD","reason":"EVIDENCE_NOT_READY"}
    if production:
        return {"decision":"ESCALATE","reason":"PRODUCTION_BOUNDARY"}
    if risk in {"HIGH","UNKNOWN"}:
        return {"decision":"ESCALATE","reason":"RISK_REQUIRES_HUMAN"}
    if risk == "LOW" and reversible:
        return {"decision":"DELEGATE","reason":"BOUNDED_NON_PRODUCTION_ACTION"}
    return {"decision":"REVIEW","reason":"NOT_WITHIN_AUTONOMOUS_ENVELOPE"}


def learn(outcome_evidence: bool, proposal: str) -> dict:
    if not outcome_evidence:
        return {"decision":"HOLD","policy_effect":"NONE"}
    return {"decision":"RECORD","proposal":proposal,"policy_effect":"PROPOSE_ONLY"}
