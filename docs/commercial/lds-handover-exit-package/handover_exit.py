#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class HandoverEvidence:
    ownership_terms_clear: bool
    deliverables_complete: bool
    export_evidence: bool
    third_party_obligations_disclosed: bool
    secure_credential_transfer_ready: bool
    access_revocation_plan_ready: bool
    customer_acceptance: bool
    unresolved_issue: bool=False

def assess(e:HandoverEvidence)->Dict:
    if e.unresolved_issue:
        return {"status":"REVIEW","reason":"UNRESOLVED_HANDOVER_ISSUE"}
    checks={
      "ownership_terms_clear":e.ownership_terms_clear,
      "deliverables_complete":e.deliverables_complete,
      "export_evidence":e.export_evidence,
      "third_party_obligations_disclosed":e.third_party_obligations_disclosed,
      "secure_credential_transfer_ready":e.secure_credential_transfer_ready,
      "access_revocation_plan_ready":e.access_revocation_plan_ready
    }
    missing=[k for k,v in checks.items() if not v]
    if missing:
        return {"status":"HOLD","reason":"HANDOVER_EVIDENCE_INCOMPLETE","missing":missing}
    if not e.customer_acceptance:
        return {"status":"CUSTOMER_ACCEPTANCE_REQUIRED","handover_complete":False}
    return {"status":"READY_TO_CLOSE","handover_complete":False,"requires_final_revocation_evidence":True}

def close_handover(customer_acceptance:bool, revocation_evidence:bool, manifest_complete:bool)->Dict:
    if not customer_acceptance:
        return {"decision":"HOLD","reason":"CUSTOMER_ACCEPTANCE_REQUIRED"}
    if not revocation_evidence:
        return {"decision":"HOLD","reason":"ACCESS_REVOCATION_EVIDENCE_REQUIRED"}
    if not manifest_complete:
        return {"decision":"HOLD","reason":"FINAL_EVIDENCE_MANIFEST_REQUIRED"}
    return {"decision":"CLOSE","status":"HANDOVER_COMPLETE"}

def plaintext_secret_allowed()->bool:
    return False
