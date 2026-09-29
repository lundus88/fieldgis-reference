"""Strategic institutions guard for LOM Virtual World."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

ALLOWED_PRIORITY={"P0","P1","P2"}

def load_registry(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_registry(r: Dict[str, Any]) -> List[str]:
    errors=[]
    if r.get("schema")!="lom.digital-nation.strategic-institutions/1":
        errors.append("SCHEMA_MISMATCH")
    if r.get("status")!="DRAFT_NON_PRODUCTION":
        errors.append("STATUS_MUST_BE_DRAFT_NON_PRODUCTION")
    if r.get("production_activation_authorized") is not False:
        errors.append("PRODUCTION_AUTHORITY_MUST_BE_FALSE")

    ids=set()
    for item in r.get("institutions",[]):
        iid=item.get("id")
        if not iid:
            errors.append("MISSING_ID")
            continue
        if iid in ids:
            errors.append(f"DUPLICATE_ID:{iid}")
        ids.add(iid)
        if item.get("priority") not in ALLOWED_PRIORITY:
            errors.append(f"INVALID_PRIORITY:{iid}")
        if not item.get("owner"):
            errors.append(f"MISSING_OWNER:{iid}")
        if not item.get("reuse"):
            errors.append(f"REUSE_REQUIRED:{iid}")
        if item.get("new_engine") is not False:
            errors.append(f"UNAPPROVED_NEW_ENGINE:{iid}")

    boundaries=set(r.get("hard_boundaries",[]))
    required={
        "No legal citizenship claim",
        "No sovereign enforcement power",
        "No AI self-succession or self-authority expansion",
        "No Production activation without explicit human gate"
    }
    for x in sorted(required-boundaries):
        errors.append(f"MISSING_HARD_BOUNDARY:{x}")
    return errors

def preview_decision(r: Dict[str, Any]) -> Dict[str, Any]:
    errors=validate_registry(r)
    return {
        "schema":"lom.digital-nation.strategic-institutions-decision/1",
        "decision":"ALLOW_PREVIEW_COMPOSITION" if not errors else "HOLD",
        "errors":errors,
        "production_authority":False,
        "sovereign_authority":False
    }
