#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class CompletionEvidence:
    target_state: str
    required_criteria: List[str]
    passed_criteria: List[str]
    evidence_refs: List[str]
    artifact_digest_present: bool
    regression_pass: bool
    customer_acceptance_required: bool=False
    customer_acceptance_present: bool=False
    stale_evidence: bool=False
    contradictory_evidence: bool=False

def evaluate_completion(e:CompletionEvidence)->Dict:
    if e.target_state not in {"BUILD_COMPLETE","QA_PASSED","DELIVERED"}:
        return {"status":"HUMAN_GATE","reason":"UNSUPPORTED_COMPLETION_STATE","completion_authorized":False}
    if e.stale_evidence or e.contradictory_evidence:
        return {"status":"HUMAN_GATE","reason":"STALE_OR_CONTRADICTORY_EVIDENCE","completion_authorized":False}
    if not e.required_criteria:
        return {"status":"HUMAN_GATE","reason":"ACCEPTANCE_CRITERIA_REQUIRED","completion_authorized":False}
    missing=sorted(set(e.required_criteria)-set(e.passed_criteria))
    if missing:
        return {"status":"AUTO","reason":"REMEDIATION_REQUIRED","missing":missing,"completion_authorized":False}
    if not e.evidence_refs or not e.artifact_digest_present:
        return {"status":"HUMAN_GATE","reason":"COMPLETION_EVIDENCE_INCOMPLETE","completion_authorized":False}
    if not e.regression_pass:
        return {"status":"AUTO","reason":"REGRESSION_REMEDIATION_REQUIRED","completion_authorized":False}
    if e.customer_acceptance_required and not e.customer_acceptance_present:
        return {"status":"AUTO_NOTIFY","reason":"WAITING_CUSTOMER_ACCEPTANCE","completion_authorized":False}
    return {
        "status":"PASS",
        "reason":"EVIDENCE_DRIVEN_COMPLETION_PASS",
        "completion_authorized":True,
        "agent_self_assertion_sufficient":False,
        "production_authority":False
    }
