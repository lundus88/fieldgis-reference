#!/usr/bin/env python3
from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, List
import json

@dataclass(frozen=True)
class IntentPackage:
    objective: str
    capability_id: str
    scope_version: int
    requirements_confirmed: bool
    approved_scope: bool
    must_have: List[str]
    acceptance_criteria: List[str]
    dependencies: List[str]
    exclusions: List[str]
    unresolved_questions: List[str]
    material_risk_hold: bool=False

def compile_work_package(i:IntentPackage)->Dict:
    if not i.requirements_confirmed:
        return {"status":"HUMAN_GATE","reason":"CONFIRMED_REQUIREMENTS_REQUIRED","executable":False}
    if not i.approved_scope or i.scope_version < 1:
        return {"status":"HUMAN_GATE","reason":"APPROVED_SCOPE_REQUIRED","executable":False}
    if not i.objective.strip() or not i.must_have:
        return {"status":"HUMAN_GATE","reason":"EXECUTION_INTENT_INCOMPLETE","executable":False}
    if not i.acceptance_criteria:
        return {"status":"HUMAN_GATE","reason":"ACCEPTANCE_CRITERIA_REQUIRED","executable":False}
    if i.unresolved_questions:
        return {"status":"HUMAN_GATE","reason":"MATERIAL_DISCOVERY_GAPS_REMAIN","items":sorted(i.unresolved_questions),"executable":False}
    if i.material_risk_hold:
        return {"status":"HUMAN_GATE","reason":"MATERIAL_RISK_HOLD","executable":False}

    work_items=[{"id":f"WP-{n+1:03d}","requirement":r,"state":"READY"} for n,r in enumerate(i.must_have)]
    tests=[{"id":f"AT-{n+1:03d}","criterion":c,"required":True} for n,c in enumerate(i.acceptance_criteria)]
    payload={
        "objective":i.objective,
        "capability_id":i.capability_id,
        "scope_version":i.scope_version,
        "work_items":work_items,
        "acceptance_tests":tests,
        "dependencies":sorted(set(i.dependencies)),
        "exclusions":sorted(set(i.exclusions)),
    }
    digest=sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {
        "status":"AUTO",
        "reason":"INTENT_COMPILED_TO_BOUNDED_WORK_PACKAGE",
        "executable":True,
        "work_package":payload,
        "work_package_digest":digest,
        "production_authority":False
    }
