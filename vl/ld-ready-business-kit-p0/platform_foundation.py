from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

from business_engine import validate_industry_pack

FOUNDATION_SCHEMA = "ld.business-platform-foundation/1"
TENANT_SCHEMA = "ld.tenant/1"
ENTITLEMENT_SCHEMA = "ld.entitlement/1"
REGISTRY_SCHEMA = "ld.industry-pack-registry/1"
RESOLVER_SCHEMA = "ld.capability-resolution/1"

PACKAGE_ORDER = ["launch", "starter", "professional", "business", "enterprise"]

ROLE_PERMISSIONS = {
    "OWNER": {"VIEW", "OPERATE", "MANAGE_MEMBERS", "CONFIGURE_PACK", "REQUEST_PACKAGE_CHANGE"},
    "ADMIN": {"VIEW", "OPERATE", "MANAGE_MEMBERS"},
    "OPERATOR": {"VIEW", "OPERATE"},
    "VIEWER": {"VIEW"},
}

CAPABILITY_DEPENDENCIES = {
    "QUOTATION": {"LEAD_CRM"},
    "ORDER": {"QUOTATION"},
    "PAYMENT": {"ORDER"},
    "RECEIPT": {"PAYMENT"},
    "MATCHING": {"LISTING", "LEAD_CRM"},
    "VIEWING": {"LISTING", "LEAD_CRM"},
    "DEAL_PIPELINE": {"LEAD_CRM", "ORDER"},
}

PACKAGE_CAPABILITIES = {
    "launch": {"AUTH", "CUSTOMER_DB", "LEAD_CRM", "NOTIFICATION"},
    "starter": {"AUTH", "CUSTOMER_DB", "LEAD_CRM", "QUOTATION", "FILE_UPLOAD", "NOTIFICATION", "PROJECT_STATUS"},
    "professional": {
        "AUTH", "CUSTOMER_DB", "LEAD_CRM", "QUOTATION", "ORDER", "PAYMENT",
        "INVOICE", "RECEIPT", "FILE_UPLOAD", "PDF_GENERATOR", "NOTIFICATION",
        "PROJECT_STATUS", "APPROVAL_WORKFLOW", "AUDIT_EVIDENCE", "AI_ASSISTANT"
    },
    "business": {
        "AUTH", "CUSTOMER_DB", "LEAD_CRM", "QUOTATION", "ORDER", "PAYMENT",
        "INVOICE", "RECEIPT", "FILE_UPLOAD", "PDF_GENERATOR", "NOTIFICATION",
        "PROJECT_STATUS", "APPROVAL_WORKFLOW", "AUDIT_EVIDENCE", "AI_ASSISTANT",
        "MAP_VIEWER", "LISTING", "MATCHING", "VIEWING", "DEAL_PIPELINE"
    },
    "enterprise": {"*"},
}

CAPABILITY_OWNERS = {
    "AUTH": "LD_IDENTITY",
    "CUSTOMER_DB": "LD_CUSTOMER_CORE",
    "LEAD_CRM": "LD_COMMERCIAL_CORE",
    "QUOTATION": "LD_COMMERCIAL_CORE",
    "ORDER": "LD_COMMERCIAL_CORE",
    "PAYMENT": "LD_PAYMENT_BOUNDARY",
    "INVOICE": "LD_FINANCEBRIDGE",
    "RECEIPT": "LD_FINANCEBRIDGE",
    "PROJECT_STATUS": "LD_DELIVERY_FACTORY",
    "FILE_UPLOAD": "LD_FILE_BOUNDARY",
    "PDF_GENERATOR": "LD_DOCUMENT_ENGINE",
    "NOTIFICATION": "LD_NOTIFICATION_BOUNDARY",
    "APPROVAL_WORKFLOW": "LD_AUTHORITY_GATE",
    "AUDIT_EVIDENCE": "LD_AUDIT_EVIDENCE",
    "AI_ASSISTANT": "LOM_INTELLIGENCE",
    "MAP_VIEWER": "LD_MAP_COMPONENT",
    "LISTING": "PROPERTY_PACK",
    "MATCHING": "PROPERTY_PACK",
    "VIEWING": "PROPERTY_PACK",
    "DEAL_PIPELINE": "PROPERTY_PACK",
}

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def validate_tenant(tenant: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(tenant, dict):
        return {"decision": "HOLD", "reason": "TENANT_REQUIRED"}
    required = ["schema", "tenant_id", "organisation_name", "organization_ref", "package", "industry_pack"]
    missing = [k for k in required if not tenant.get(k)]
    if missing:
        return {"decision": "HOLD", "reason": "TENANT_INCOMPLETE", "missing": sorted(missing)}
    if tenant["schema"] != TENANT_SCHEMA:
        return {"decision": "HOLD", "reason": "TENANT_SCHEMA_UNSUPPORTED"}
    if not _SLUG.fullmatch(str(tenant["tenant_id"])):
        return {"decision": "HOLD", "reason": "TENANT_ID_INVALID"}
    if tenant["package"] not in PACKAGE_ORDER:
        return {"decision": "HOLD", "reason": "PACKAGE_UNSUPPORTED"}
    if tenant.get("production_write_authority", False):
        return {"decision": "HOLD", "reason": "TENANT_CANNOT_GRANT_PRODUCTION_WRITE"}
    if not str(tenant["organization_ref"]).strip():
        return {"decision": "HOLD", "reason": "ORGANIZATION_BINDING_REQUIRED"}
    return {"decision": "ALLOW", "digest": _digest(tenant)}

def authorize_tenant_action(tenant: dict[str, Any], actor: dict[str, Any], action: str) -> dict[str, Any]:
    tv = validate_tenant(tenant)
    if tv["decision"] != "ALLOW":
        return tv
    if not isinstance(actor, dict) or not actor.get("principal_id"):
        return {"decision": "HOLD", "reason": "ACTOR_CONTEXT_REQUIRED"}

    evidence = actor.get("membership_evidence")
    if not isinstance(evidence, dict):
        return {"decision": "HOLD", "reason": "MEMBERSHIP_EVIDENCE_REQUIRED"}
    required = ["verified", "evidence_ref", "organization_ref", "role"]
    missing = [k for k in required if evidence.get(k) in (None, "")]
    if missing:
        return {"decision": "HOLD", "reason": "MEMBERSHIP_EVIDENCE_INCOMPLETE", "missing": sorted(missing)}
    if evidence.get("verified") is not True:
        return {"decision": "HOLD", "reason": "MEMBERSHIP_NOT_VERIFIED"}
    if evidence["organization_ref"] != tenant["organization_ref"]:
        return {"decision": "HOLD", "reason": "CROSS_TENANT_ACCESS_DENIED"}

    role = str(evidence["role"]).upper()
    if role not in ROLE_PERMISSIONS:
        return {"decision": "HOLD", "reason": "ROLE_UNSUPPORTED"}
    if action not in ROLE_PERMISSIONS[role]:
        return {"decision": "HOLD", "reason": "ROLE_PERMISSION_DENIED", "role": role, "action": action}

    authority_evidence = {
        "principal_id": actor["principal_id"],
        "evidence_ref": evidence["evidence_ref"],
        "organization_ref": evidence["organization_ref"],
        "role": role,
        "action": action,
    }
    return {
        "decision": "ALLOW",
        "tenant_id": tenant["tenant_id"],
        "organization_ref": tenant["organization_ref"],
        "principal_id": actor["principal_id"],
        "role": role,
        "action": action,
        "authority_evidence_digest": _digest(authority_evidence),
        "production_authority": False,
        "live_charging_authority": False,
    }

def validate_capability_dependencies(requested_capabilities: list[str]) -> dict[str, Any]:
    requested = set(requested_capabilities)
    missing = {}
    for capability in sorted(requested):
        required = CAPABILITY_DEPENDENCIES.get(capability, set())
        absent = sorted(required - requested)
        if absent:
            missing[capability] = absent
    if missing:
        return {"decision": "HOLD", "reason": "CAPABILITY_DEPENDENCY_MISSING", "missing": missing}
    return {"decision": "ALLOW"}

def evaluate_package_change(tenant: dict[str, Any], new_package: str, active_capabilities: list[str]) -> dict[str, Any]:
    tv = validate_tenant(tenant)
    if tv["decision"] != "ALLOW":
        return tv
    if new_package not in PACKAGE_ORDER:
        return {"decision": "HOLD", "reason": "PACKAGE_UNSUPPORTED"}
    if new_package == tenant["package"]:
        return {"decision": "ALLOW", "reason": "NO_CHANGE"}
    allowed = PACKAGE_CAPABILITIES[new_package]
    active = set(active_capabilities or [])
    removed = [] if "*" in allowed else sorted(active - allowed)
    return {
        "decision": "HUMAN_GATE",
        "reason": "PACKAGE_CHANGE_HUMAN_APPROVAL_REQUIRED",
        "from_package": tenant["package"],
        "to_package": new_package,
        "capabilities_removed_from_entitlement": removed,
        "data_deletion_authorized": False,
        "automatic_upgrade_authorized": False,
    }

def resolve_entitlement(tenant: dict[str, Any], requested_capabilities: list[str]) -> dict[str, Any]:
    tv = validate_tenant(tenant)
    if tv["decision"] != "ALLOW":
        return tv
    if not isinstance(requested_capabilities, list) or not requested_capabilities:
        return {"decision": "HOLD", "reason": "CAPABILITY_REQUEST_REQUIRED"}
    package = tenant["package"]
    allowed = PACKAGE_CAPABILITIES[package]
    requested = sorted(set(requested_capabilities))
    denied = [] if "*" in allowed else sorted(set(requested) - allowed)
    if denied:
        return {
            "decision": "HOLD",
            "reason": "ENTITLEMENT_DENIED",
            "package": package,
            "denied": denied,
        }
    return {
        "decision": "ALLOW",
        "schema": ENTITLEMENT_SCHEMA,
        "tenant_id": tenant["tenant_id"],
        "package": package,
        "capabilities": requested,
        "entitlement_digest": _digest({
            "tenant_id": tenant["tenant_id"],
            "package": package,
            "capabilities": requested,
        }),
        "production": "LOCKED",
    }

def build_pack_registry(packs: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(packs, list) or not packs:
        return {"decision": "HOLD", "reason": "PACKS_REQUIRED"}
    ids = []
    entries = []
    for pack in packs:
        validation = validate_industry_pack(pack)
        if validation["decision"] != "ALLOW":
            return {
                "decision": "HOLD",
                "reason": "PACK_REGISTRY_VALIDATION_FAILED",
                "validation": validation,
            }
        if pack.get("production", "LOCKED") != "LOCKED":
            return {"decision": "HOLD", "reason": "PACK_PRODUCTION_MUST_BE_LOCKED"}

        pack_id = pack["pack_id"]
        vertical = pack["vertical"]
        capabilities = pack["capabilities"]
        if pack_id in ids:
            return {"decision": "HOLD", "reason": "PACK_ID_DUPLICATE", "pack_id": pack_id}
        ids.append(pack_id)
        entries.append({
            "pack_id": pack_id,
            "vertical": vertical,
            "capabilities": sorted(set(capabilities)),
            "pack_digest": validation["digest"],
            "production": "LOCKED",
        })
    entries = sorted(entries, key=lambda x: x["pack_id"])
    return {
        "decision": "ALLOW",
        "schema": REGISTRY_SCHEMA,
        "packs": entries,
        "registry_digest": _digest(entries),
        "production": "LOCKED",
    }

def resolve_capabilities(requested_capabilities: list[str]) -> dict[str, Any]:
    if not isinstance(requested_capabilities, list) or not requested_capabilities:
        return {"decision": "HOLD", "reason": "CAPABILITY_REQUEST_REQUIRED"}
    requested = sorted(set(requested_capabilities))
    dependency = validate_capability_dependencies(requested)
    if dependency["decision"] != "ALLOW":
        return dependency
    unknown = sorted(set(requested) - set(CAPABILITY_OWNERS))
    if unknown:
        return {
            "decision": "HOLD",
            "reason": "CAPABILITY_OWNER_UNKNOWN",
            "unknown": unknown,
            "action": "REVIEW_BEFORE_BUILD",
        }
    bindings = [{"capability": c, "owner": CAPABILITY_OWNERS[c], "action": "REUSE"} for c in requested]
    return {
        "decision": "ALLOW",
        "schema": RESOLVER_SCHEMA,
        "bindings": bindings,
        "build_new": [],
        "policy": "REUSE_BEFORE_BUILD",
        "resolution_digest": _digest(bindings),
    }

def compose_tenant_runtime(
    tenant: dict[str, Any],
    pack: dict[str, Any],
) -> dict[str, Any]:
    registry = build_pack_registry([pack])
    if registry["decision"] != "ALLOW":
        return registry
    if tenant.get("industry_pack") != pack.get("pack_id"):
        return {"decision": "HOLD", "reason": "TENANT_PACK_MISMATCH"}
    ent = resolve_entitlement(tenant, pack.get("capabilities", []))
    if ent["decision"] != "ALLOW":
        return ent
    resolution = resolve_capabilities(pack.get("capabilities", []))
    if resolution["decision"] != "ALLOW":
        return resolution
    return {
        "decision": "ALLOW",
        "schema": FOUNDATION_SCHEMA,
        "tenant_id": tenant["tenant_id"],
        "industry_pack": pack["pack_id"],
        "tenant_digest": validate_tenant(tenant)["digest"],
        "registry_digest": registry["registry_digest"],
        "entitlement_digest": ent["entitlement_digest"],
        "resolution_digest": resolution["resolution_digest"],
        "production": "LOCKED",
        "live_charging": "LOCKED",
        "authority": {
            "production_deploy": "HUMAN_ONLY",
            "live_charging": "HUMAN_ONLY",
            "privilege_widening": "HUMAN_ONLY",
        },
    }
