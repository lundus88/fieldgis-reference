package lom.governance_test

import rego.v1
import data.lom.governance

base_input := {
    "action_id": "RUN_TEST",
    "evidence_ids": ["ev-1"],
    "production": false,
    "risk": "LOW",
    "self_approval": false,
    "protected_main_merge": false,
    "authority_known": true,
}

test_bounded_non_production_allow if {
    governance.decision == {
        "decision": "ALLOW",
        "reason": "BOUNDED_NON_PRODUCTION",
        "autonomous_ceiling": "PREPARE_PR",
    } with input as base_input
}

test_missing_evidence_holds_first if {
    governance.decision == {"decision": "HOLD", "reason": "MISSING_EVIDENCE"} with input as object.union(base_input, {
        "evidence_ids": [],
        "production": true,
    })
}

test_unknown_authority_holds if {
    governance.decision == {"decision": "HOLD", "reason": "UNKNOWN_AUTHORITY"} with input as object.union(base_input, {
        "authority_known": false,
    })
}

test_self_approval_holds if {
    governance.decision == {"decision": "HOLD", "reason": "SELF_APPROVAL_FORBIDDEN"} with input as object.union(base_input, {
        "self_approval": true,
    })
}

test_protected_main_human_gate if {
    governance.decision == {"decision": "HUMAN_GATE", "reason": "PROTECTED_MAIN_HUMAN_ONLY"} with input as object.union(base_input, {
        "protected_main_merge": true,
    })
}

test_production_human_gate if {
    governance.decision == {"decision": "HUMAN_GATE", "reason": "PRODUCTION_HUMAN_ONLY"} with input as object.union(base_input, {
        "production": true,
    })
}

test_registered_human_only_action_human_gates if {
    governance.decision == {"decision": "HUMAN_GATE", "reason": "HUMAN_ONLY_ACTION"} with input as object.union(base_input, {
        "action_id": "FINANCIAL_COMMITMENT",
    })
}

test_high_risk_human_gate if {
    governance.decision == {"decision": "HUMAN_GATE", "reason": "HIGH_RISK"} with input as object.union(base_input, {
        "risk": "HIGH",
    })
}

test_unknown_risk_holds if {
    governance.decision == {"decision": "HOLD", "reason": "UNKNOWN_RISK"} with input as object.union(base_input, {
        "risk": "UNKNOWN",
    })
}

test_unregistered_action_holds if {
    governance.decision == {"decision": "HOLD", "reason": "UNREGISTERED_ACTION"} with input as object.union(base_input, {
        "action_id": "ATTACKER_DEFINED_ACTION",
    })
}
