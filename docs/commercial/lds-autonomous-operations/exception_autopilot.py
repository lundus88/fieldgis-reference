#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

PLAYBOOKS={
    "BUILD_TEST_FAILURE":"REPAIR_AND_RETEST",
    "DEPENDENCY_TRANSIENT_FAILURE":"BACKOFF_AND_RETRY",
    "NONPRODUCTION_DEPLOY_FAILURE":"ROLLBACK_REPAIR_RETEST",
    "PROVIDER_TRANSIENT_OUTAGE":"WAIT_RETRY_WITH_BACKOFF",
    "CUSTOMER_INPUT_MISSING":"ROUTE_CUSTOMER_DEPENDENCY",
}

@dataclass(frozen=True)
class ExceptionEvidence:
    failure_class: str
    retry_count: int
    max_retries: int
    estimated_next_cost: float
    remaining_cost_budget: float
    rollback_evidence: bool
    deterministic_failure: bool=False
    security_signal: bool=False
    production_impact: bool=False
    irreversible_customer_impact: bool=False
    repeated_loop_detected: bool=False

def decide(e:ExceptionEvidence)->Dict:
    if e.security_signal:
        return {"status":"HUMAN_GATE","reason":"SECURITY_SIGNAL","circuit_breaker":True}
    if e.production_impact or e.irreversible_customer_impact:
        return {"status":"HUMAN_GATE","reason":"CONSEQUENTIAL_BOUNDARY","circuit_breaker":True}
    if e.repeated_loop_detected:
        return {"status":"HUMAN_GATE","reason":"AUTONOMOUS_LOOP_DETECTED","circuit_breaker":True}
    if e.retry_count >= e.max_retries:
        return {"status":"HUMAN_GATE","reason":"RETRY_BUDGET_EXHAUSTED","circuit_breaker":False}
    if e.estimated_next_cost > e.remaining_cost_budget:
        return {"status":"HUMAN_GATE","reason":"COST_BUDGET_EXCEEDED","circuit_breaker":False}
    if e.deterministic_failure:
        return {"status":"HUMAN_GATE","reason":"DETERMINISTIC_FAILURE_REQUIRES_DIAGNOSIS","circuit_breaker":False}
    playbook=PLAYBOOKS.get(e.failure_class)
    if not playbook:
        return {"status":"HUMAN_GATE","reason":"NO_APPROVED_RECOVERY_PLAYBOOK","circuit_breaker":False}
    if "ROLLBACK" in playbook and not e.rollback_evidence:
        return {"status":"HUMAN_GATE","reason":"ROLLBACK_EVIDENCE_REQUIRED","circuit_breaker":False}
    return {
        "status":"AUTO_NOTIFY",
        "reason":"APPROVED_EXCEPTION_PLAYBOOK",
        "playbook":playbook,
        "next":"EXECUTE_BOUNDED_RECOVERY_THEN_RETEST",
        "production_authority":False
    }
