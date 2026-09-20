#!/usr/bin/env python3
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Dict, Tuple, FrozenSet
import json

ROOT=Path(__file__).resolve().parent
GRAPH=json.loads((ROOT/"state_graph.json").read_text())
TRANSITIONS={(x["from"],x["to"]):x for x in GRAPH["transitions"]}

@dataclass(frozen=True)
class AuthorityReceipt:
    org_id:str
    actor_id:str
    approved_at:str
    human_approved:bool
    evidence_refs:Tuple[str,...]
    idempotency_key:str

@dataclass(frozen=True)
class TransitionRequest:
    org_id:str
    from_state:str
    to_state:str
    evidence:FrozenSet[str]
    dependencies:Dict[str,bool]
    authority:AuthorityReceipt
    stale_or_contradictory:bool=False
    material_scope_change:bool=False
    change_request_approved:bool=False

def _receipt_digest(r:TransitionRequest)->str:
    payload={
      "org_id":r.org_id,
      "from_state":r.from_state,
      "to_state":r.to_state,
      "actor_id":r.authority.actor_id,
      "approved_at":r.authority.approved_at,
      "evidence_refs":sorted(r.authority.evidence_refs),
      "dependency_snapshot":{k:bool(r.dependencies[k]) for k in sorted(r.dependencies)},
      "idempotency_key":r.authority.idempotency_key
    }
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    return sha256(raw).hexdigest()

def evaluate_transition(r:TransitionRequest, consumed_keys:FrozenSet[str]=frozenset())->Dict:
    edge=TRANSITIONS.get((r.from_state,r.to_state))
    if edge is None:
        return {"status":"HOLD","reason":"ILLEGAL_STATE_TRANSITION","transition_authorized":False}

    if not r.authority.idempotency_key:
        return {"status":"HOLD","reason":"IDEMPOTENCY_KEY_REQUIRED","transition_authorized":False}
    if r.authority.idempotency_key in consumed_keys:
        return {"status":"IDEMPOTENT_REPLAY","reason":"TRANSITION_ALREADY_PROCESSED","transition_authorized":False}

    if not r.org_id or r.authority.org_id != r.org_id:
        return {"status":"HOLD","reason":"CROSS_ORGANIZATION_AUTHORITY_DENIED","transition_authorized":False}

    if r.stale_or_contradictory:
        return {"status":"HOLD","reason":"STALE_OR_CONTRADICTORY_HARD_GATE_EVIDENCE","transition_authorized":False}

    if r.material_scope_change and not r.change_request_approved:
        return {"status":"HOLD","reason":"APPROVED_CHANGE_REQUEST_REQUIRED","transition_authorized":False}

    missing_dep=[d for d in edge.get("dependencies",[]) if not r.dependencies.get(d,False)]
    if missing_dep:
        return {"status":"HOLD","reason":"DEPENDENCY_NOT_READY","missing_dependencies":sorted(missing_dep),"transition_authorized":False}

    missing_evidence=[e for e in edge.get("evidence",[]) if e not in r.evidence]
    if missing_evidence:
        return {"status":"HOLD","reason":"REQUIRED_EVIDENCE_MISSING","missing_evidence":sorted(missing_evidence),"transition_authorized":False}

    any_evidence=edge.get("any_evidence",[])
    if any_evidence and not any(e in r.evidence for e in any_evidence):
        return {"status":"HOLD","reason":"ANY_OF_REQUIRED_EVIDENCE_MISSING","acceptable_evidence":sorted(any_evidence),"transition_authorized":False}

    if edge.get("human_authority") and not r.authority.human_approved:
        return {"status":"HOLD","reason":"EXPLICIT_HUMAN_AUTHORITY_REQUIRED","transition_authorized":False}

    if "human_kickoff_approval" in r.evidence and not r.authority.human_approved:
        return {"status":"HOLD","reason":"EXPLICIT_HUMAN_AUTHORITY_REQUIRED","transition_authorized":False}

    if r.to_state=="PAYMENT_RECONCILED" and "payment_redirect" in r.evidence and "authoritative_payment_reconciliation" not in r.evidence:
        return {"status":"HOLD","reason":"PAYMENT_REDIRECT_NOT_RECONCILIATION","transition_authorized":False}

    digest=_receipt_digest(r)
    return {
      "status":"PASS",
      "reason":"TRANSITION_EVIDENCE_COMPLETE",
      "transition_authorized":True,
      "receipt_digest":digest,
      "idempotency_key":r.authority.idempotency_key,
      "source_truth_mutated":False,
      "production_authority":"HUMAN_ONLY"
    }

# Compatibility coarse gate retained for callers of v1.
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
    autonomous_kickoff_eligible: bool=False

def evaluate(e:LifecycleEvidence)->Dict:
    if e.stale_or_contradictory:
        return {"status":"HOLD","reason":"STALE_OR_CONTRADICTORY_HARD_GATE_EVIDENCE","next_stage":None}
    if not e.approved_scope:
        return {"status":"HOLD","reason":"APPROVED_SCOPE_REQUIRED","next_stage":"BLUEPRINT_APPROVED"}
    if not e.human_approved_quotation:
        return {"status":"HOLD","reason":"HUMAN_APPROVED_QUOTATION_REQUIRED","next_stage":"QUOTATION_APPROVED"}
    if not e.payment_reconciled:
        return {"status":"HOLD","reason":"PAYMENT_RECONCILIATION_REQUIRED","next_stage":"PAYMENT_RECONCILED"}
    if not e.kickoff_ready:
        return {"status":"HOLD","reason":"KICKOFF_READY_REQUIRED","next_stage":"KICKOFF_APPROVED"}
    if not (e.human_kickoff_approved or e.autonomous_kickoff_eligible):
        return {"status":"HOLD","reason":"KICKOFF_GATE_REQUIRED","next_stage":"KICKOFF_APPROVED"}
    if e.material_scope_change and not e.change_request_approved:
        return {"status":"HOLD","reason":"APPROVED_CHANGE_REQUEST_REQUIRED","next_stage":"BUILDING"}
    if not e.build_complete:
        return {"status":"IN_PROGRESS","reason":"BUILD_IN_PROGRESS","next_stage":"BUILDING"}
    if not e.qa_evidence:
        return {"status":"HOLD","reason":"QA_EVIDENCE_REQUIRED","next_stage":"QA_PASSED"}
    if not e.customer_acceptance_evidence:
        return {"status":"HOLD","reason":"CUSTOMER_ACCEPTANCE_REQUIRED","next_stage":"CUSTOMER_ACCEPTED"}
    if not e.delivery_evidence:
        return {"status":"HOLD","reason":"DELIVERY_EVIDENCE_REQUIRED","next_stage":"DELIVERED"}
    return {"status":"DELIVERY_COMPLETE","reason":"MANDATORY_LIFECYCLE_EVIDENCE_COMPLETE","next_stage":"SUPPORT_ACTIVE","production_authority":"HUMAN_ONLY","source_truth_mutated":False}

def advisory_can_advance_hard_gate()->bool:
    return False
