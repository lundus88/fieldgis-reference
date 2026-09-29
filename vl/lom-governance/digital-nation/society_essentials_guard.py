"""LOM Virtual World Society Essentials guard."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List

ALLOWED_PRIORITY={"P0","P1","P2"}

def load_registry(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def validate_registry(r: Dict[str, Any]) -> List[str]:
    errors=[]
    if r.get("schema")!="lom.digital-nation.society-essentials/1":
        errors.append("SCHEMA_MISMATCH")
    if r.get("status")!="DRAFT_NON_PRODUCTION":
        errors.append("STATUS_MUST_BE_DRAFT_NON_PRODUCTION")
    if r.get("production_activation_authorized") is not False:
        errors.append("PRODUCTION_AUTHORITY_MUST_BE_FALSE")

    ids=set()
    for item in r.get("capabilities",[]):
        cid=item.get("id")
        if not cid:
            errors.append("MISSING_ID")
            continue
        if cid in ids:
            errors.append(f"DUPLICATE_ID:{cid}")
        ids.add(cid)
        if item.get("priority") not in ALLOWED_PRIORITY:
            errors.append(f"INVALID_PRIORITY:{cid}")
        if not item.get("owner"):
            errors.append(f"MISSING_OWNER:{cid}")
        if not item.get("reuse"):
            errors.append(f"REUSE_REQUIRED:{cid}")
        if item.get("new_engine") is not False:
            errors.append(f"UNAPPROVED_NEW_ENGINE:{cid}")
    return errors

def preview_decision(r: Dict[str, Any]) -> Dict[str, Any]:
    errors=validate_registry(r)
    return {
        "schema":"lom.digital-nation.society-essentials-decision/1",
        "decision":"ALLOW_PREVIEW_COMPOSITION" if not errors else "HOLD",
        "errors":errors,
        "production_authority":False
    }
