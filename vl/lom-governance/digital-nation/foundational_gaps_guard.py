"""Guard for LOM Virtual World foundational gaps closure."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

EXPECTED={
    "persistent_world_state_runtime":"P0",
    "economic_bootstrapping_liquidity":"P0",
    "jurisdiction_compliance_router":"P0",
    "delegated_authority_permission_wallet":"P0",
    "policy_lifecycle_change_control":"P1",
    "market_fairness_economic_integrity":"P1",
    "world_simulation_sandbox":"P1",
    "culture_social_cohesion":"P1",
}

def load_registry(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_registry(r: Dict[str, Any]) -> List[str]:
    errors=[]
    if r.get("schema")!="lom.digital-nation.foundational-gaps-closure/1":
        errors.append("SCHEMA_MISMATCH")
    if r.get("status")!="DRAFT_NON_PRODUCTION":
        errors.append("STATUS_MUST_BE_DRAFT_NON_PRODUCTION")
    if r.get("production_activation_authorized") is not False:
        errors.append("PRODUCTION_AUTHORITY_MUST_BE_FALSE")

    caps=r.get("capabilities",[])
    by_id={x.get("id"):x for x in caps}
    if set(by_id)!=set(EXPECTED):
        errors.append("FOUNDATION_SET_MISMATCH")

    for cid,priority in EXPECTED.items():
        item=by_id.get(cid)
        if not item:
            continue
        if item.get("priority")!=priority:
            errors.append(f"PRIORITY_MISMATCH:{cid}")
        if not item.get("owner"):
            errors.append(f"MISSING_OWNER:{cid}")
        if not item.get("reuse"):
            errors.append(f"REUSE_REQUIRED:{cid}")
        if item.get("new_engine") is not False:
            errors.append(f"UNAPPROVED_NEW_ENGINE:{cid}")

    inv=set(r.get("invariants",[]))
    required={
        "World-state projection is never a second source of truth.",
        "Liquidity mechanisms must not fabricate demand, transactions, reviews or revenue.",
        "Unsupported or unknown jurisdiction conditions fail to MANUAL_REVIEW.",
        "Delegated authority is monotonic-restrictive and auditable.",
        "AI cannot self-amend authority or policy.",
        "Synthetic evidence is never real-world evidence.",
        "Production activation remains explicit human authority."
    }
    for x in sorted(required-inv):
        errors.append(f"MISSING_INVARIANT:{x}")

    return errors

def preview_decision(r: Dict[str, Any]) -> Dict[str, Any]:
    errors=validate_registry(r)
    return {
        "schema":"lom.digital-nation.foundational-gaps-closure-decision/1",
        "decision":"ALLOW_PREVIEW_COMPOSITION" if not errors else "HOLD",
        "errors":errors,
        "production_authority":False,
        "live_financial_authority":False
    }
