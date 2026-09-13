ALLOWED_OUTCOMES = {"WON", "LOST", "NO_BID", "HOLD", "MONITOR"}
TERMINAL_OUTCOMES = {"WON", "LOST", "NO_BID"}


def evaluate_outcome(record):
    outcome = record.get("outcome")
    if outcome not in ALLOWED_OUTCOMES:
        return {
            "status": "HOLD",
            "learning_status": "EVIDENCE_UNAVAILABLE",
            "reason": "Invalid or missing outcome state",
            "policy_change_allowed": False,
        }

    evidence_ref = record.get("evidence_ref")
    explicit_gap = bool(record.get("evidence_gap"))
    reason = record.get("outcome_reason")

    if not evidence_ref and not explicit_gap:
        return {
            "status": "HOLD",
            "learning_status": "EVIDENCE_UNAVAILABLE",
            "reason": "Outcome evidence is missing",
            "policy_change_allowed": False,
        }

    if not reason:
        return {
            "status": "HOLD",
            "learning_status": "EVIDENCE_INCOMPLETE",
            "reason": "Outcome reason is missing",
            "policy_change_allowed": False,
        }

    if outcome in TERMINAL_OUTCOMES and explicit_gap and not evidence_ref:
        return {
            "status": "HOLD",
            "learning_status": "EVIDENCE_GAP",
            "reason": "Terminal outcome is not evidence-confirmed",
            "policy_change_allowed": False,
        }

    terminal = outcome in TERMINAL_OUTCOMES
    return {
        "status": outcome,
        "learning_status": "READY" if terminal else "NON_TERMINAL_SIGNAL",
        "reason": reason,
        "policy_change_allowed": False,
    }


def build_learning_record(record):
    assessment = evaluate_outcome(record)
    lesson = record.get("lesson")
    recommendation = record.get("policy_recommendation")

    return {
        "outcome": assessment["status"],
        "learning_status": assessment["learning_status"],
        "reason": assessment["reason"],
        "lesson": lesson if lesson else None,
        "policy_recommendation": recommendation if recommendation else None,
        "policy_change_mode": "HUMAN_REVIEW_ONLY",
        "auto_apply": False,
    }
