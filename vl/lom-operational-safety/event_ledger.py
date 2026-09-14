import hashlib
import json

ALLOWED_STATES = {"PLANNED", "RUNNING", "VALIDATING", "REMEDIATING", "COMPLETE", "HOLD", "ESCALATE", "FAIL"}


def _hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class AppendOnlyEventLedger:
    def __init__(self):
        self._events = []

    @property
    def events(self):
        return tuple(dict(event) for event in self._events)

    def append(self, run_id, objective_id, actor_id, action_id, evidence_refs,
               from_state, to_state, reason, timestamp_epoch):
        if to_state not in ALLOWED_STATES:
            raise ValueError("UNKNOWN_STATE")
        sequence = len(self._events) + 1
        prev_hash = self._events[-1]["event_hash"] if self._events else "GENESIS"
        body = {
            "sequence": sequence,
            "run_id": run_id,
            "objective_id": objective_id,
            "actor_id": actor_id,
            "action_id": action_id,
            "evidence_refs": list(evidence_refs),
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
            "timestamp_epoch": timestamp_epoch,
            "prev_hash": prev_hash,
        }
        body["event_hash"] = _hash(body)
        self._events.append(body)
        return dict(body)

    def verify(self):
        prev_hash = "GENESIS"
        for expected_sequence, event in enumerate(self._events, start=1):
            if event["sequence"] != expected_sequence or event["prev_hash"] != prev_hash:
                return False
            candidate = dict(event)
            stored_hash = candidate.pop("event_hash")
            if _hash(candidate) != stored_hash:
                return False
            prev_hash = stored_hash
        return True

    def replace(self, *_args, **_kwargs):
        raise RuntimeError("APPEND_ONLY_LEDGER")

    def delete(self, *_args, **_kwargs):
        raise RuntimeError("APPEND_ONLY_LEDGER")
