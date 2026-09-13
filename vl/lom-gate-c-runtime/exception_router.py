from typing import Dict, Any

DIRECTOR_QUEUE = "DIRECTOR_EXCEPTION_QUEUE"
RISK_QUEUE = "RISK_GOVERNOR_QUEUE"
EVIDENCE_QUEUE = "EVIDENCE_REQUEST_QUEUE"
RETRY_QUEUE = "RETRY_QUEUE"

ROUTES = {
    "HUMAN_ONLY_ACTION": DIRECTOR_QUEUE,
    "UNKNOWN_AUTHORITY": DIRECTOR_QUEUE,
    "RISK_THRESHOLD_EXCEEDED": RISK_QUEUE,
    "SECURITY_POLICY_CHANGE": RISK_QUEUE,
    "PRODUCTION_BOUNDARY": DIRECTOR_QUEUE,
    "FINANCIAL_OR_CONTRACTUAL_COMMITMENT": DIRECTOR_QUEUE,
    "MISSING_REQUIRED_EVIDENCE": EVIDENCE_QUEUE,
    "CONTRADICTORY_EVIDENCE": EVIDENCE_QUEUE,
    "VALIDATION_FAILED": EVIDENCE_QUEUE,
    "TRANSIENT_TOOL_ERROR": RETRY_QUEUE,
    "TEMPORARY_UNAVAILABLE": RETRY_QUEUE,
    "RETRY_EXHAUSTED": DIRECTOR_QUEUE,
    "SELF_CERTIFICATION_FORBIDDEN": DIRECTOR_QUEUE,
}

def route(exception: Dict[str, Any]) -> Dict[str, Any]:
    error_class = exception.get("error_class")
    destination = ROUTES.get(error_class, DIRECTOR_QUEUE)
    return {
        "task_id": exception.get("task_id"),
        "error_class": error_class or "UNKNOWN_EXCEPTION",
        "destination": destination,
        "requires_human_attention": destination == DIRECTOR_QUEUE,
        "evidence": list(exception.get("evidence", [])),
    }
