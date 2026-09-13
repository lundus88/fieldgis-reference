from dataclasses import dataclass

HUMAN_ONLY_STATES = {"ESCALATE"}

@dataclass(frozen=True)
class MissionInput:
    objective_id: str
    lifecycle_state: str
    evidence_status: str
    risk_state: str
    agent_states: tuple
    exceptions: tuple = ()


def build_snapshot(data: MissionInput) -> dict:
    if not data.objective_id:
        raise ValueError("objective_id required")
    action = "NONE"
    state = data.lifecycle_state
    exceptions = list(data.exceptions)

    if data.evidence_status in {"MISSING", "CONTRADICTORY"}:
        state = "HOLD"
        action = "ACQUIRE_EVIDENCE"
        exceptions.append("EVIDENCE_NOT_READY")
    elif data.risk_state in {"HIGH", "UNKNOWN"}:
        state = "ESCALATE"
        action = "APPROVE_OR_REJECT"
        exceptions.append("RISK_REQUIRES_DIRECTOR")
    elif data.lifecycle_state in HUMAN_ONLY_STATES:
        action = "APPROVE_OR_REJECT"
    elif data.lifecycle_state == "HOLD":
        action = "REVIEW"

    return {
        "objective_id": data.objective_id,
        "lifecycle_state": state,
        "evidence_status": data.evidence_status,
        "risk_state": data.risk_state,
        "agent_states": [{"role": r, "state": s} for r, s in data.agent_states],
        "exceptions": exceptions,
        "recommended_director_action": action,
    }
