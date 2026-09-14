import json
from pathlib import Path

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": 3}


class ActionRegistry:
    def __init__(self, registry):
        if registry.get("default_decision") != "DENY":
            raise ValueError("ACTION_REGISTRY_MUST_DEFAULT_DENY")
        if registry.get("production_locked") is not True:
            raise ValueError("ACTION_REGISTRY_PRODUCTION_LOCK_REQUIRED")
        self.actions = {item["action_id"]: item for item in registry.get("actions", [])}
        self.human_only = set(registry.get("human_only_actions", []))

    @classmethod
    def from_path(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def authorize(self, action_id, capability_id, risk, reversible, production):
        if action_id in self.human_only:
            return {"decision": "ESCALATE", "reason": "HUMAN_ONLY_ACTION"}
        action = self.actions.get(action_id)
        if action is None:
            return {"decision": "HOLD", "reason": "UNREGISTERED_ACTION"}
        if capability_id != action["capability_id"]:
            return {"decision": "HOLD", "reason": "CAPABILITY_MISMATCH"}
        if production:
            return {"decision": "ESCALATE", "reason": "PRODUCTION_BOUNDARY"}
        if risk not in RISK_ORDER or RISK_ORDER[risk] > RISK_ORDER[action["max_risk"]]:
            return {"decision": "ESCALATE", "reason": "RISK_CEILING_EXCEEDED"}
        if action.get("reversible_required") and not reversible:
            return {"decision": "HOLD", "reason": "REVERSIBILITY_REQUIRED"}
        return {"decision": "DELEGATE", "reason": "REGISTERED_BOUNDED_ACTION"}
