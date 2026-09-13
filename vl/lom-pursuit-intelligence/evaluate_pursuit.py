def evaluate(item):
    if item.get("route") == "WATCH_FOR_REPEAT":
        return {
            "decision": "WATCHLIST",
            "reason": "Historical or repeat-market signal",
            "next_best_action": item.get("next_evidence_action", "Refresh evidence."),
        }

    required = {
        "target_identity": "target identity",
        "scope_status": "scope",
        "economic_fit": "economic fit",
        "deadline_status": "deadline/status",
        "eligibility": "eligibility",
        "intent": "intent",
    }

    missing = []
    for key, label in required.items():
        value = item.get(key)
        if value in (None, "", "UNKNOWN", "UNCONFIRMED"):
            missing.append(label)

    if missing:
        return {
            "decision": "HOLD",
            "reason": "Missing critical evidence: " + ", ".join(missing),
            "next_best_action": item.get("next_evidence_action", "Acquire missing evidence."),
        }

    return {
        "decision": "CONTINUE",
        "reason": "Minimum pursuit evidence is present",
        "next_best_action": item.get("next_evidence_action", "Prepare human-reviewed pursuit package."),
    }
