"""Guard for the 12 Advanced Society Fundamentals."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

EXPECTED=[
    "rule_of_law_institutions",
    "productive_economy",
    "financial_capital_system",
    "education_human_capital",
    "science_technology_innovation",
    "infrastructure",
    "administrative_capacity",
    "security_resilience",
    "health_social_protection",
    "financial_management",
    "global_economic_relations",
    "continuous_improvement",
]
MATURITY={"DEFINED","TESTED","PREVIEW_PROVEN","PILOT_PROVEN","PRODUCTION_PROVEN"}

def load_registry(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_registry(r: Dict[str, Any]) -> List[str]:
    errors=[]
    if r.get("schema")!="lom.digital-nation.advanced-society-fundamentals/1":
        errors.append("SCHEMA_MISMATCH")
    if r.get("status")!="DRAFT_NON_PRODUCTION":
        errors.append("STATUS_MUST_BE_DRAFT_NON_PRODUCTION")
    if r.get("production_activation_authorized") is not False:
        errors.append("PRODUCTION_AUTHORITY_MUST_BE_FALSE")

    pillars=r.get("pillars",[])
    ids=[p.get("id") for p in pillars]
    if ids!=EXPECTED:
        errors.append("TWELVE_PILLAR_SET_OR_ORDER_MISMATCH")
    if len(set(ids))!=12:
        errors.append("PILLAR_COUNT_OR_DUPLICATE_ERROR")

    for i,p in enumerate(pillars,1):
        if p.get("order")!=i:
            errors.append(f"ORDER_MISMATCH:{p.get('id')}")
        if not p.get("owner"):
            errors.append(f"MISSING_OWNER:{p.get('id')}")
        if not p.get("reuse"):
            errors.append(f"REUSE_REQUIRED:{p.get('id')}")
        if not p.get("target"):
            errors.append(f"MISSING_TARGET:{p.get('id')}")

    if set(r.get("maturity_stages",[]))!=MATURITY:
        errors.append("MATURITY_MODEL_MISMATCH")

    boundaries=set(r.get("hard_boundaries",[]))
    for req in [
        "No AI self-authority expansion",
        "No person or AI bypasses active authority evidence and audit controls",
        "Production activation remains explicit human authority"
    ]:
        if req not in boundaries:
            errors.append(f"MISSING_HARD_BOUNDARY:{req}")
    return errors

def preview_decision(r: Dict[str, Any]) -> Dict[str, Any]:
    errors=validate_registry(r)
    return {
        "schema":"lom.digital-nation.advanced-society-fundamentals-decision/1",
        "decision":"ALLOW_PREVIEW_COMPOSITION" if not errors else "HOLD",
        "errors":errors,
        "production_authority":False,
        "sovereign_authority":False
    }
