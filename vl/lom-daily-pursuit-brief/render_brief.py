ATTENTION_ACTIONS = {"REVIEW_PURSUIT", "ACQUIRE_EVIDENCE"}
VALID_ACTIONS = ATTENTION_ACTIONS | {"MONITOR"}


def render(queue, max_attention=5):
    if not isinstance(queue, list):
        return {
            "status": "EVIDENCE_UNAVAILABLE",
            "summary": {"REVIEW_PURSUIT": 0, "ACQUIRE_EVIDENCE": 0, "MONITOR": 0},
            "attention": [],
            "monitor_count": 0,
        }

    summary = {"REVIEW_PURSUIT": 0, "ACQUIRE_EVIDENCE": 0, "MONITOR": 0}
    attention = []

    for item in queue:
        action = item.get("director_action")
        if action not in VALID_ACTIONS:
            return {
                "status": "EVIDENCE_UNAVAILABLE",
                "summary": summary,
                "attention": [],
                "monitor_count": 0,
            }
        summary[action] += 1
        if action in ATTENTION_ACTIONS:
            attention.append({
                "queue_rank": item.get("queue_rank"),
                "director_action": action,
                "pursuit_decision": item.get("pursuit_decision"),
                "urgency_score": item.get("urgency_score", 0),
                "evidence_gap_count": item.get("evidence_gap_count", 0),
                "reason": item.get("reason"),
                "next_best_action": item.get("next_best_action") or "Acquire missing evidence.",
            })

    attention.sort(key=lambda x: (x["queue_rank"] is None, x["queue_rank"] if x["queue_rank"] is not None else 10**9))
    return {
        "status": "READY",
        "summary": summary,
        "attention": attention[:max_attention],
        "monitor_count": summary["MONITOR"],
    }
