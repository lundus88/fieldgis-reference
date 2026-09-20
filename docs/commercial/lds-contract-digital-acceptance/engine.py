#!/usr/bin/env python3
from dataclasses import dataclass
from hashlib import sha256
from typing import Tuple, Dict

@dataclass(frozen=True)
class AcceptanceInput:
    customer_id:str
    document_hashes:Tuple[str,...]
    scope_version:str
    terms_version:str
    acceptance_action:str
    accepted_at:str
    evidence_id:str

def create_record(x:AcceptanceInput)->Dict:
    if not all([x.customer_id,x.document_hashes,x.scope_version,x.terms_version,x.acceptance_action,x.accepted_at,x.evidence_id]):
        return {"status":"REVIEW","reason":"INCOMPLETE_ACCEPTANCE_EVIDENCE"}
    if x.acceptance_action not in {"EXPLICIT_ACCEPT","SIGNED_ACCEPT"}:
        return {"status":"REVIEW","reason":"EXPLICIT_ACCEPTANCE_REQUIRED"}
    payload="|".join([x.customer_id,*x.document_hashes,x.scope_version,x.terms_version,x.acceptance_action,x.accepted_at,x.evidence_id])
    rid=sha256(payload.encode()).hexdigest()
    return {"status":"ACCEPTANCE_RECORDED","acceptance_record_id":rid,"bound_document_hashes":list(x.document_hashes),"immutable":True}

def infer_consent_from_silence()->bool:
    return False
