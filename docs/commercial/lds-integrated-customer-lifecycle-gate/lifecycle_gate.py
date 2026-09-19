#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class LifecycleEvidence:
    approved_scope: bool
    human_approved_quotation: bool
    payment_reconciled: bool
    kickoff_ready: bool
    human_kickoff_approved: bool
    build_complete: bool
    qa_evidence: bool
    customer_acceptance_evidence: bool
    delivery_evidence: bool
    material_scope_change: bool=False
    change_request_approved: bool=False
    stale_or_contradictory: bool=False

ORDER=[
 "ASSESSMENT","BLUEPRINT","PRICING_REVIEW","QUOTATION","PAYMENT_RECONCILIATION",
 "KICKOFF","BUILD","QA","UAT","DELIVERY","SUPPORT","RENEWAL_OR_EXIT"
]

def evaluate(e:LifecycleEvidence)->Dict:
    if e.stale_or_contradictory:
        return {"status":"HOLD","reason":"STALE_OR_CONTRADICTORY_HARD_GATE_EVIDENCE","next_stage":None}
    if not e.approved_scope:
        return {"status":"HOLD","reason":"APPROVED_SCOPE_REQUIRED","next_stage":"BLUEPRINT"}
    if not e.human_approved_quotation:
        return {"status":"HOLD","reason":"HUMAN_APPROVED_QUOTATION_REQUIRED","next_stage":"QUOTATION"}
    if not e.payment_reconciled:
        return {"status":"HOLD","reason":"PAYMENT_RECONCILIATION_REQUIRED","next_stage":"PAYMENT_RECONCILIATION"}
    if not e.kickoff_ready or not e.human_kickoff_approved:
        return {"status":"HOLD","reason":"KICKOFF_GATE_REQUIRED","next_stage":"KICKOFF"}
    if e.material_scope_change and not e.change_request_approved:
        return {"status":"HOLD","reason":"APPROVED_CHANGE_REQUEST_REQUIRED","next_stage":"BUILD"}
    if not e.build_complete:
        return {"status":"IN_PROGRESS","reason":"BUILD_IN_PROGRESS","next_stage":"BUILD"}
    if not e.qa_evidence:
        return {"status":"HOLD","reason":"QA_EVIDENCE_REQUIRED","next_stage":"QA"}
    if not e.customer_acceptance_evidence:
        return {"status":"HOLD","reason":"CUSTOMER_ACCEPTANCE_REQUIRED","next_stage":"UAT"}
    if not e.delivery_evidence:
        return {"status":"HOLD","reason":"DELIVERY_EVIDENCE_REQUIRED","next_stage":"DELIVERY"}
    return {
      "status":"DELIVERY_COMPLETE",
      "reason":"MANDATORY_LIFECYCLE_EVIDENCE_COMPLETE",
      "next_stage":"SUPPORT",
      "production_authority":"HUMAN_ONLY",
      "source_truth_mutated":False
    }

def advisory_can_advance_hard_gate()->bool:
    return False
