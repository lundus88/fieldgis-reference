"""Guard for LOM Global Nation Benchmark framework."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

FORBIDDEN={"overall_country_score","country_rank","political_system_winner","copy_whole_country_model"}
DECISIONS={"UNRESEARCHED","HOLD","REFERENCE_ONLY","PILOT","ABSORB","REJECT"}

def load_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_registry(r: Dict[str, Any]) -> List[str]:
    errors=[]
    if r.get("schema")!="lom.global-nation-benchmark/1":
        errors.append("SCHEMA_MISMATCH")
    if r.get("status")!="DRAFT_RESEARCH_NON_PRODUCTION":
        errors.append("STATUS_MISMATCH")
    if r.get("production_activation_authorized") is not False:
        errors.append("PRODUCTION_AUTHORITY_MUST_BE_FALSE")

    countries=r.get("country_pool",[])
    if not 20 <= len(countries) <= 30:
        errors.append("COUNTRY_POOL_MUST_BE_20_TO_30")
    if len(countries)!=len(set(countries)):
        errors.append("DUPLICATE_COUNTRY")

    dimensions=r.get("dimensions",[])
    if len(dimensions)<30:
        errors.append("AT_LEAST_30_DIMENSIONS_REQUIRED")
    if len(dimensions)!=len(set(dimensions)):
        errors.append("DUPLICATE_DIMENSION")

    if set(r.get("decision_states",[]))!=DECISIONS:
        errors.append("DECISION_STATE_MISMATCH")

    forbidden=set(r.get("forbidden_outputs",[]))
    for item in FORBIDDEN:
        if item not in forbidden:
            errors.append(f"MISSING_FORBIDDEN_OUTPUT:{item}")

    required_criteria={"evidence","compatibility","risk","value","scalability","auditability","security","legal","economic","governance","duplication","reversibility"}
    if not required_criteria.issubset(set(r.get("absorption_criteria",[]))):
        errors.append("ABSORPTION_CRITERIA_INCOMPLETE")
    return errors

def validate_hypotheses(h: Dict[str, Any]) -> List[str]:
    errors=[]
    if h.get("schema")!="lom.global-nation-benchmark.hypotheses/1":
        errors.append("HYPOTHESIS_SCHEMA_MISMATCH")
    for item in h.get("hypotheses",[]):
        if item.get("evidence_status")!="UNVERIFIED_FOR_LOM":
            errors.append(f"HYPOTHESIS_PREMATURELY_PROMOTED:{item.get('economy')}")
        if not item.get("candidate_areas"):
            errors.append(f"HYPOTHESIS_AREAS_REQUIRED:{item.get('economy')}")
    return errors

def preview_decision(registry: Dict[str, Any], hypotheses: Dict[str, Any]) -> Dict[str, Any]:
    errors=validate_registry(registry)+validate_hypotheses(hypotheses)
    return {
        "schema":"lom.global-nation-benchmark.decision/1",
        "decision":"ALLOW_RESEARCH" if not errors else "HOLD",
        "errors":errors,
        "country_ranking_authority":False,
        "political_winner_authority":False,
        "production_authority":False
    }
