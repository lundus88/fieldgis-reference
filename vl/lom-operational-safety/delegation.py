RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": 3}


def validate_actor_separation(executor_actor_id, validator_actor_id, remediator_actor_id=None):
    if not executor_actor_id or not validator_actor_id:
        return {"decision": "HOLD", "reason": "ACTOR_ID_REQUIRED"}
    if executor_actor_id == validator_actor_id:
        return {"decision": "HOLD", "reason": "EXECUTOR_VALIDATOR_COLLISION"}
    if remediator_actor_id and remediator_actor_id == validator_actor_id:
        return {"decision": "HOLD", "reason": "REMEDIATOR_VALIDATOR_COLLISION"}
    return {"decision": "ALLOW", "reason": "ACTOR_SEPARATION_OK"}


def validate_delegation(parent, child, now_epoch):
    required = {"environment", "capability_ids", "risk_ceiling", "expires_at_epoch", "max_attempts"}
    if not required.issubset(parent) or not required.issubset(child):
        return {"decision": "HOLD", "reason": "DELEGATION_ENVELOPE_INCOMPLETE"}
    if parent["environment"] != "NON_PRODUCTION" or child["environment"] != "NON_PRODUCTION":
        return {"decision": "ESCALATE", "reason": "NON_PRODUCTION_ENVIRONMENT_REQUIRED"}
    if now_epoch >= int(child["expires_at_epoch"]):
        return {"decision": "HOLD", "reason": "DELEGATION_EXPIRED"}
    if int(child["expires_at_epoch"]) > int(parent["expires_at_epoch"]):
        return {"decision": "HOLD", "reason": "DELEGATION_EXPIRY_WIDENED"}
    if not set(child["capability_ids"]).issubset(set(parent["capability_ids"])):
        return {"decision": "HOLD", "reason": "DELEGATION_CAPABILITY_WIDENED"}
    if RISK_ORDER.get(child["risk_ceiling"], 99) > RISK_ORDER.get(parent["risk_ceiling"], -1):
        return {"decision": "HOLD", "reason": "DELEGATION_RISK_WIDENED"}
    if int(child["max_attempts"]) > int(parent["max_attempts"]):
        return {"decision": "HOLD", "reason": "DELEGATION_ATTEMPTS_WIDENED"}
    if int(child["max_attempts"]) < 1:
        return {"decision": "HOLD", "reason": "INVALID_ATTEMPT_BUDGET"}
    return {"decision": "ALLOW", "reason": "DELEGATION_NON_EXPANDING"}


def validate_attempt(attempt, max_attempts):
    if attempt < 1:
        return {"decision": "HOLD", "reason": "INVALID_ATTEMPT_NUMBER"}
    if attempt > max_attempts:
        return {"decision": "HOLD", "reason": "ATTEMPT_BUDGET_EXHAUSTED"}
    return {"decision": "ALLOW", "reason": "ATTEMPT_WITHIN_BUDGET"}
