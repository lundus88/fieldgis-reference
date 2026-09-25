from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from platform_foundation import (
    CAPABILITY_OWNERS,
    authorize_tenant_action,
    compose_tenant_runtime,
)

SCHEMA = "ld.business-engine-integration/1"

SURFACE_REGISTRY = {
    "CUSTOMER_PORTAL": {
        "owner": "LD_CLIENT_PORTAL",
        "source": "commercial/lundus-digital-systems/client_portal_state.py",
        "contract": "commercial/lundus-digital-systems/client-portal-contract.json",
        "required_capabilities": {
            "AUTH", "CUSTOMER_DB", "PROJECT_STATUS", "QUOTATION",
            "PAYMENT", "INVOICE", "RECEIPT", "AUDIT_EVIDENCE",
        },
        "mode": "READ_ONLY",
        "execution_authority": "NONE",
    },
    "DELIVERY_FACTORY": {
        "owner": "LD_DELIVERY_FACTORY",
        "source": "vl/ld-ready-business-kit-p0/ready_business_p1.py",
        "contract": "vl/ld-ready-business-kit-p0/P1_DELIVERY_FACTORY.md",
        "required_capabilities": {
            "PROJECT_STATUS", "FILE_UPLOAD", "PDF_GENERATOR",
            "APPROVAL_WORKFLOW", "AUDIT_EVIDENCE",
        },
        "mode": "BOUNDED_WORKFLOW",
        "execution_authority": "EXISTING_GATES_ONLY",
    },
    "PRICING_INTELLIGENCE": {
        "owner": "LD_PRICING_ESTIMATION_INTELLIGENCE",
        "source": "docs/commercial/lds-pricing-estimation-intelligence/pricing_estimation.py",
        "contract": "docs/commercial/lds-pricing-estimation-intelligence/contract.json",
        "required_capabilities": {"QUOTATION", "AUDIT_EVIDENCE"},
        "mode": "ADVISORY_READ_ONLY",
        "execution_authority": "NONE",
    },
    "PROFITABILITY_CAPACITY": {
        "owner": "LD_PROJECT_PROFITABILITY_CAPACITY",
        "source": "docs/commercial/lds-project-profitability-capacity/profitability_capacity.py",
        "contract": "docs/commercial/lds-project-profitability-capacity/contract.json",
        "required_capabilities": {"ORDER", "PAYMENT", "AUDIT_EVIDENCE"},
        "mode": "ADVISORY_READ_ONLY",
        "execution_authority": "NONE",
    },
    "EXECUTIVE_MISSION_CONTROL": {
        "owner": "LD_EXECUTIVE_COMMERCIAL_MISSION_CONTROL",
        "source": "docs/commercial/lds-executive-commercial-mission-control/executive_commercial.py",
        "contract": "docs/commercial/lds-executive-commercial-mission-control/contract.json",
        "required_capabilities": {"AUDIT_EVIDENCE"},
        "mode": "READ_ONLY",
        "execution_authority": "NONE",
    },
}

HUMAN_ONLY_ACTIONS = {
    "FINAL_PRICE_APPROVAL",
    "CUSTOMER_QUOTATION_RELEASE",
    "LIVE_CHARGE",
    "REFUND_EXCEPTION",
    "PRODUCTION_DEPLOY",
    "PRIVILEGE_WIDENING",
    "DESTRUCTIVE_PRODUCTION_ACTION",
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def validate_surface_registry() -> dict[str, Any]:
    allowed_modes = {"READ_ONLY", "ADVISORY_READ_ONLY", "BOUNDED_WORKFLOW"}
    for surface, entry in sorted(SURFACE_REGISTRY.items()):
        required = {"owner", "source", "contract", "required_capabilities", "mode", "execution_authority"}
        missing = sorted(required - set(entry))
        if missing:
            return {
                "decision": "HOLD",
                "reason": "SURFACE_REGISTRY_INCOMPLETE",
                "surface": surface,
                "missing": missing,
            }
        if entry["mode"] not in allowed_modes:
            return {"decision": "HOLD", "reason": "SURFACE_MODE_UNSUPPORTED", "surface": surface}
        unknown = sorted(set(entry["required_capabilities"]) - set(CAPABILITY_OWNERS))
        if unknown:
            return {
                "decision": "HOLD",
                "reason": "SURFACE_CAPABILITY_UNKNOWN",
                "surface": surface,
                "unknown": unknown,
            }
        if entry["execution_authority"] not in {"NONE", "EXISTING_GATES_ONLY"}:
            return {
                "decision": "HOLD",
                "reason": "SURFACE_AUTHORITY_WIDENING",
                "surface": surface,
            }
    return {
        "decision": "ALLOW",
        "schema": SCHEMA,
        "registry_digest": _digest(SURFACE_REGISTRY),
    }

def compose_integration_plan(
    tenant: dict[str, Any],
    pack: dict[str, Any],
    actor: dict[str, Any],
    surfaces: list[str],
) -> dict[str, Any]:
    registry = validate_surface_registry()
    if registry["decision"] != "ALLOW":
        return registry

    runtime = compose_tenant_runtime(tenant, pack)
    if runtime.get("decision") != "ALLOW":
        return runtime

    access = authorize_tenant_action(tenant, actor, "VIEW")
    if access.get("decision") != "ALLOW":
        return access

    if not isinstance(surfaces, list) or not surfaces:
        return {"decision": "HOLD", "reason": "INTEGRATION_SURFACES_REQUIRED"}

    unknown_surfaces = sorted(set(surfaces) - set(SURFACE_REGISTRY))
    if unknown_surfaces:
        return {
            "decision": "HOLD",
            "reason": "INTEGRATION_SURFACE_UNKNOWN",
            "unknown": unknown_surfaces,
        }

    pack_caps = set(pack.get("capabilities", []))
    bindings = []
    for surface in sorted(set(surfaces)):
        entry = SURFACE_REGISTRY[surface]
        missing_caps = sorted(set(entry["required_capabilities"]) - pack_caps)
        if missing_caps:
            return {
                "decision": "HOLD",
                "reason": "SURFACE_CAPABILITY_MISSING",
                "surface": surface,
                "missing": missing_caps,
            }
        bindings.append({
            "surface": surface,
            "owner": entry["owner"],
            "source": entry["source"],
            "contract": entry["contract"],
            "mode": entry["mode"],
            "execution_authority": entry["execution_authority"],
            "action": "REUSE",
        })

    plan = {
        "schema": SCHEMA,
        "tenant_id": tenant["tenant_id"],
        "organization_ref": tenant["organization_ref"],
        "industry_pack": pack["pack_id"],
        "surfaces": bindings,
        "production": "LOCKED",
        "live_charging": "LOCKED",
        "customer_price_authority": "HUMAN_ONLY",
        "production_deploy_authority": "HUMAN_ONLY",
        "new_generic_engines": [],
        "policy": "REUSE_EXISTING_SOURCE_OF_TRUTH",
    }
    return {
        "decision": "ALLOW",
        "plan": plan,
        "plan_digest": _digest(plan),
        "authority_evidence_digest": access["authority_evidence_digest"],
    }

def request_action(plan_result: dict[str, Any], action: str) -> dict[str, Any]:
    if plan_result.get("decision") != "ALLOW":
        return {"decision": "HOLD", "reason": "INTEGRATION_PLAN_NOT_READY"}
    if action in HUMAN_ONLY_ACTIONS:
        return {
            "decision": "HUMAN_GATE",
            "reason": "HUMAN_ONLY_ACTION",
            "action": action,
            "automatic_execution": False,
        }
    return {
        "decision": "HOLD",
        "reason": "ACTION_NOT_AUTHORIZED_BY_INTEGRATION_LAYER",
        "action": action,
        "automatic_execution": False,
    }
