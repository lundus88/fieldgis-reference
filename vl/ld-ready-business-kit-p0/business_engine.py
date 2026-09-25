from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

SCHEMA = "ld.business-engine/1"
PACK_SCHEMA = "ld.industry-pack/1"

CANONICAL_STATES = [
    "VISITOR",
    "ASSESSMENT",
    "QUALIFIED",
    "BLUEPRINT_APPROVED",
    "QUOTATION_APPROVED",
    "CONTRACT_ACCEPTED",
    "PAYMENT_RECONCILED",
    "KICKOFF_APPROVED",
    "BUILDING",
    "QA_PASSED",
    "CUSTOMER_ACCEPTED",
    "DELIVERED",
    "SUPPORT_ACTIVE",
    "CLOSED",
]

CORE_CAPABILITIES = {
    "AUTH",
    "CUSTOMER_DB",
    "LEAD_CRM",
    "QUOTATION",
    "ORDER",
    "PAYMENT",
    "INVOICE",
    "RECEIPT",
    "PROJECT_STATUS",
    "FILE_UPLOAD",
    "PDF_GENERATOR",
    "NOTIFICATION",
    "APPROVAL_WORKFLOW",
    "AUDIT_EVIDENCE",
    "AI_ASSISTANT",
}

HUMAN_ONLY = {
    "FINAL_PRICING",
    "DISCOUNT_EXCEPTION",
    "CUSTOMER_COMMITMENT",
    "PRODUCTION_DEPLOY",
    "LIVE_CHARGING",
    "PRIVILEGE_WIDENING",
    "DESTRUCTIVE_PRODUCTION_ACTION",
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def validate_industry_pack(pack: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(pack, dict):
        return {"decision": "HOLD", "reason": "PACK_REQUIRED"}
    required = ["schema", "pack_id", "name", "vertical", "capabilities", "entities", "workflows", "human_gates"]
    missing = [k for k in required if not pack.get(k)]
    if missing:
        return {"decision": "HOLD", "reason": "PACK_INCOMPLETE", "missing": sorted(missing)}
    if pack["schema"] != PACK_SCHEMA:
        return {"decision": "HOLD", "reason": "PACK_SCHEMA_UNSUPPORTED"}
    caps = pack.get("capabilities")
    if not isinstance(caps, list) or not caps:
        return {"decision": "HOLD", "reason": "PACK_CAPABILITIES_INVALID"}
    unknown = sorted(set(caps) - CORE_CAPABILITIES - {"MAP_VIEWER", "LISTING", "MATCHING", "VIEWING", "DEAL_PIPELINE"})
    if unknown:
        return {"decision": "HOLD", "reason": "PACK_CAPABILITY_UNKNOWN", "unknown": unknown}
    gates = set(pack.get("human_gates", []))
    if not HUMAN_ONLY.issuperset(gates):
        return {"decision": "HOLD", "reason": "PACK_HUMAN_GATE_UNKNOWN"}
    workflows = pack.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        return {"decision": "HOLD", "reason": "PACK_WORKFLOWS_INVALID"}
    return {"decision": "ALLOW", "digest": _digest(pack)}

def engine_manifest(pack: dict[str, Any]) -> dict[str, Any]:
    verdict = validate_industry_pack(pack)
    if verdict["decision"] != "ALLOW":
        return verdict
    return {
        "decision": "ALLOW",
        "schema": SCHEMA,
        "pack_id": pack["pack_id"],
        "vertical": pack["vertical"],
        "pack_digest": verdict["digest"],
        "canonical_states": CANONICAL_STATES,
        "core_capabilities": sorted(CORE_CAPABILITIES),
        "production": "LOCKED",
        "live_charging": "LOCKED",
        "human_approval_required": True,
        "authority": {
            "production_deploy": "HUMAN_ONLY",
            "live_charging": "HUMAN_ONLY",
            "customer_commitment": "HUMAN_ONLY",
        },
    }
