WEIGHTS = {"CONTINUE": 300, "HOLD": 200, "WATCHLIST": 100}
ACTIONS = {"CONTINUE": "REVIEW_PURSUIT", "HOLD": "ACQUIRE_EVIDENCE", "WATCHLIST": "MONITOR"}


def build_queue(items):
    queue = []
    for index, item in enumerate(items):
        decision = item.get("decision")
        if decision not in WEIGHTS:
            decision = "HOLD"
        urgency = item.get("deadline_urgency", 0)
        gaps = item.get("evidence_gap_count", 0)
        if not isinstance(urgency, int) or not 0 <= urgency <= 100:
            raise ValueError("deadline_urgency must be 0..100")
        if not isinstance(gaps, int) or gaps < 0:
            raise ValueError("evidence_gap_count must be >= 0")
        queue.append({
            "source_index": index,
            "pursuit_decision": decision,
            "director_action": ACTIONS[decision],
            "urgency_score": urgency,
            "evidence_gap_count": gaps,
            "priority_score": WEIGHTS[decision] + urgency - min(gaps, 50),
            "next_best_action": item.get("next_best_action") or "Acquire missing evidence.",
        })
    queue.sort(key=lambda x: (-x["priority_score"], x["source_index"]))
    for rank, item in enumerate(queue, start=1):
        item["queue_rank"] = rank
    return queue
