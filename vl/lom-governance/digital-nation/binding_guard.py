"""LOM Digital Nation adapter binding guard.

Validates that unresolved or unmerged dependencies cannot be promoted as active
and that non-production bindings cannot accidentally advertise Production authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_STATUS = {
    "BOUND_PREVIEW",
    "PARTIAL_PREVIEW",
    "HOLD_PENDING_DEPENDENCY",
    "HOLD_UNRESOLVED_OWNER",
}


def load_manifest(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest(manifest: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if manifest.get("schema") != "lom.digital-nation.adapter-bindings/1":
        errors.append("SCHEMA_MISMATCH")
    if manifest.get("status") != "DRAFT_NON_PRODUCTION":
        errors.append("STATUS_MUST_BE_DRAFT_NON_PRODUCTION")

    ids = set()
    for item in manifest.get("bindings", []):
        binding_id = item.get("id")
        if not binding_id:
            errors.append("MISSING_BINDING_ID")
            continue
        if binding_id in ids:
            errors.append(f"DUPLICATE_BINDING_ID:{binding_id}")
        ids.add(binding_id)

        status = item.get("binding_status")
        if status not in ALLOWED_STATUS:
            errors.append(f"INVALID_BINDING_STATUS:{binding_id}")

        if item.get("production_authorized") is not False:
            errors.append(f"PRODUCTION_AUTHORITY_MUST_BE_FALSE:{binding_id}")

        if status == "HOLD_PENDING_DEPENDENCY":
            if not item.get("dependency_pr"):
                errors.append(f"MISSING_DEPENDENCY_PR:{binding_id}")
            if item.get("source_ref") == "main":
                errors.append(f"PENDING_DEPENDENCY_CANNOT_BIND_MAIN:{binding_id}")

        if status == "HOLD_UNRESOLVED_OWNER":
            if item.get("owner") != "UNRESOLVED":
                errors.append(f"UNRESOLVED_OWNER_MARKER_REQUIRED:{binding_id}")

        if status in {"BOUND_PREVIEW", "PARTIAL_PREVIEW"}:
            for field in ("owner", "source_repo", "source_ref", "source_path"):
                if not item.get(field):
                    errors.append(f"MISSING_{field.upper()}:{binding_id}")

    return errors


def activation_decision(manifest: Dict[str, Any]) -> Dict[str, Any]:
    errors = validate_manifest(manifest)
    holds = [
        b["id"]
        for b in manifest.get("bindings", [])
        if str(b.get("binding_status", "")).startswith("HOLD_")
    ]
    return {
        "schema": "lom.digital-nation.adapter-binding-decision/1",
        "mode": "PREVIEW_ONLY",
        "decision": "HOLD" if errors or holds else "READY_FOR_PREVIEW_BINDING",
        "errors": errors,
        "hold_bindings": holds,
        "production_authority": False,
    }
