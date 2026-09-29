"""LOM Virtual World Golden Journey Preview preflight.

This module never activates Production. It checks whether the Digital Nation
Preview can legitimately execute the complete Golden World Journey using only
declared adapter bindings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from binding_guard import activation_decision, validate_manifest


REQUIRED_BINDINGS = {
    "identity_authority",
    "business_registry",
    "payment",
    "affiliate",
    "economic_participation",
    "education_skill",
    "reputation",
    "dispute",
}


def load_bindings(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def preview_preflight(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    errors = validate_manifest(dict(manifest))
    by_id = {b.get("id"): b for b in manifest.get("bindings", [])}
    missing = sorted(REQUIRED_BINDINGS - set(by_id))
    if missing:
        errors.extend(f"MISSING_REQUIRED_BINDING:{x}" for x in missing)

    holds = sorted(
        b["id"]
        for b in manifest.get("bindings", [])
        if str(b.get("binding_status", "")).startswith("HOLD_")
    )
    not_preview_bound = sorted(
        bid for bid in REQUIRED_BINDINGS
        if bid in by_id and by_id[bid].get("binding_status") not in {"BOUND_PREVIEW", "PARTIAL_PREVIEW"}
    )

    return {
        "schema": "lom.digital-nation.golden-world-preflight/1",
        "mode": "PREVIEW_ONLY",
        "decision": "READY_FOR_SYNTHETIC_GOLDEN_JOURNEY" if not errors and not holds and not not_preview_bound else "HOLD",
        "errors": errors,
        "hold_bindings": holds,
        "not_preview_bound": not_preview_bound,
        "production_authority": False,
        "live_payment_authority": False,
        "live_payout_authority": False,
    }


def main() -> int:
    root = Path(__file__).resolve().parent
    report = preview_preflight(load_bindings(root / "adapter-bindings-v1.json"))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["decision"] == "READY_FOR_SYNTHETIC_GOLDEN_JOURNEY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
