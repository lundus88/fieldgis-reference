#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class ProofEvidence:
    evidence_present: bool
    verification_pass: bool
    permission_required: bool
    permission_valid: bool
    claim_has_limitations: bool
    fabricated_or_unverifiable_claim: bool=False

def publication_state(e:ProofEvidence)->Dict:
    if e.fabricated_or_unverifiable_claim:
        return {"state":"HOLD","reason":"UNVERIFIABLE_OR_FABRICATED_CLAIM"}
    if not e.evidence_present or not e.verification_pass:
        return {"state":"INTERNAL_ONLY","reason":"EVIDENCE_NOT_READY"}
    if e.permission_required and not e.permission_valid:
        return {"state":"INTERNAL_ONLY","reason":"CUSTOMER_PERMISSION_REQUIRED"}
    if not e.claim_has_limitations:
        return {"state":"INTERNAL_ONLY","reason":"CLAIM_LIMITATIONS_REQUIRED"}
    return {"state":"PUBLISHABLE","reason":"PROOF_GATES_PASS"}
