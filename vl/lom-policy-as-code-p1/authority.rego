package lom.governance

import rego.v1

bounded_action if {
    some action in data.lom.bounded_actions
    action.action_id == input.action_id
}

human_only_action if {
    input.action_id in data.lom.human_only_actions
}

decision := {"decision": "HOLD", "reason": "MISSING_EVIDENCE"} if {
    count(input.evidence_ids) == 0
} else := {"decision": "HOLD", "reason": "UNKNOWN_AUTHORITY"} if {
    input.authority_known == false
} else := {"decision": "HOLD", "reason": "SELF_APPROVAL_FORBIDDEN"} if {
    input.self_approval == true
} else := {"decision": "HUMAN_GATE", "reason": "PROTECTED_MAIN_HUMAN_ONLY"} if {
    input.protected_main_merge == true
} else := {"decision": "HUMAN_GATE", "reason": "PRODUCTION_HUMAN_ONLY"} if {
    input.production == true
} else := {"decision": "HUMAN_GATE", "reason": "HUMAN_ONLY_ACTION"} if {
    human_only_action
} else := {"decision": "HUMAN_GATE", "reason": "HIGH_RISK"} if {
    input.risk == "HIGH"
} else := {"decision": "HOLD", "reason": "UNKNOWN_RISK"} if {
    input.risk == "UNKNOWN"
} else := {"decision": "HOLD", "reason": "UNREGISTERED_ACTION"} if {
    not bounded_action
} else := {
    "decision": "ALLOW",
    "reason": "BOUNDED_NON_PRODUCTION",
    "autonomous_ceiling": data.lom.authority.autonomous_ceiling,
} if {
    bounded_action
    input.production == false
}
