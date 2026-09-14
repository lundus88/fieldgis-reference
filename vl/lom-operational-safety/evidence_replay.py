class ReplayGuard:
    def __init__(self):
        self._seen = set()

    def claim(self, run_id, objective_id, idempotency_key):
        if not run_id or not objective_id or not idempotency_key:
            return {"decision": "HOLD", "reason": "IDEMPOTENCY_ID_REQUIRED"}
        key = (run_id, objective_id, idempotency_key)
        if key in self._seen:
            return {"decision": "HOLD", "reason": "DUPLICATE_OR_REPLAY"}
        self._seen.add(key)
        return {"decision": "ALLOW", "reason": "IDEMPOTENCY_CLAIMED"}


def validate_evidence(status, observed_at_epoch, now_epoch, max_age_seconds, contradictory=False):
    if contradictory or status == "CONTRADICTORY":
        return {"decision": "HOLD", "reason": "CONTRADICTORY_EVIDENCE"}
    if status in {"MISSING", "UNKNOWN", ""}:
        return {"decision": "HOLD", "reason": "EVIDENCE_NOT_READY"}
    if observed_at_epoch > now_epoch:
        return {"decision": "HOLD", "reason": "EVIDENCE_TIMESTAMP_INVALID"}
    if now_epoch - observed_at_epoch > max_age_seconds:
        return {"decision": "HOLD", "reason": "STALE_EVIDENCE"}
    return {"decision": "ALLOW", "reason": "EVIDENCE_FRESH"}
