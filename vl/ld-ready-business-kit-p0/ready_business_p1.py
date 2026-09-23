from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from ready_business_kit import render_preview, validate_onboarding

PACKAGE_REFERENCE = {
    "starter": {
        "label": "LD Business Starter",
        "indicative_setup_myr": 199,
        "customer_price_authority": "HUMAN_ONLY",
    },
    "smart": {
        "label": "LD Smart Business",
        "indicative_monthly_myr": [29, 49],
        "customer_price_authority": "HUMAN_ONLY",
    },
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def create_client_project(onboarding: dict[str, Any], package_key: str = "starter") -> dict[str, Any]:
    validated = validate_onboarding(onboarding)
    if validated["decision"] != "ALLOW":
        return validated
    if package_key not in PACKAGE_REFERENCE:
        return {"decision": "HOLD", "reason": "PACKAGE_UNSUPPORTED"}

    preview = render_preview(onboarding)
    if preview["decision"] != "ALLOW":
        return preview

    project_seed = {
        "business_name": onboarding["business_name"],
        "vertical": onboarding["vertical"],
        "whatsapp": onboarding["whatsapp"],
        "onboarding_digest": validated["digest"],
        "package_key": package_key,
    }
    project_id = "LD-" + _digest(project_seed)[:12].upper()

    proposal = {
        "schema": "ld.proposal-draft/1",
        "project_id": project_id,
        "customer_business_name": onboarding["business_name"],
        "package": PACKAGE_REFERENCE[package_key]["label"],
        "scope": [
            "configured one-page business site",
            "WhatsApp CTA",
            "vertical content cards",
            "maps/social links when supplied",
            "preview and QA",
        ],
        "price_status": "HUMAN_REQUIRED",
        "final_price": None,
        "discount": None,
        "customer_commitment": "NOT_CREATED",
        "release_status": "DRAFT_INTERNAL_ONLY",
    }

    quotation = {
        "schema": "ld.quotation-draft/1",
        "project_id": project_id,
        "status": "DRAFT_HUMAN_REVIEW",
        "currency": "MYR",
        "amount": None,
        "pricing_reference": PACKAGE_REFERENCE[package_key],
        "final_amount_authority": "HUMAN_ONLY",
        "customer_release": "HUMAN_ONLY",
        "payment_request": "DISABLED",
    }

    workspace = {
        "schema": "ld.delivery-workspace/1",
        "project_id": project_id,
        "state": "WAITING_HUMAN_COMMERCIAL_APPROVAL",
        "vertical": onboarding["vertical"],
        "package_key": package_key,
        "onboarding_digest": validated["digest"],
        "preview_manifest": preview["manifest"],
        "checklist": {
            "onboarding_validated": True,
            "preview_generated": True,
            "proposal_drafted": True,
            "quotation_drafted": True,
            "pricing_human_approved": False,
            "customer_release_human_approved": False,
            "customer_acceptance_evidence": False,
            "domain_control_evidence": False,
            "production_publish_human_approved": False,
        },
        "payment": "DISABLED",
        "production": "LOCKED",
    }

    return {
        "decision": "ALLOW",
        "project_id": project_id,
        "preview_html": preview["html"],
        "proposal": proposal,
        "quotation": quotation,
        "workspace": workspace,
    }

def approve_pricing(project: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    if project.get("decision") != "ALLOW":
        return {"decision": "HOLD", "reason": "PROJECT_NOT_READY"}
    if approval.get("decision") != "APPROVE" or not approval.get("human_approver"):
        return {"decision": "HUMAN_GATE", "reason": "PRICING_APPROVAL_REQUIRED"}
    amount = approval.get("amount")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return {"decision": "HOLD", "reason": "APPROVED_AMOUNT_INVALID"}

    out=json.loads(json.dumps(project))
    out["quotation"]["amount"]=amount
    out["quotation"]["status"]="PRICE_APPROVED_INTERNAL"
    out["proposal"]["final_price"]=amount
    out["proposal"]["price_status"]="HUMAN_APPROVED_INTERNAL"
    out["workspace"]["checklist"]["pricing_human_approved"]=True
    out["workspace"]["state"]="WAITING_HUMAN_CUSTOMER_RELEASE"
    out["pricing_approval_evidence"]={
        "human_approver":approval["human_approver"],
        "decision":"APPROVE",
        "amount":amount,
    }
    return out

def authorize_customer_release(project: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    if not project.get("workspace",{}).get("checklist",{}).get("pricing_human_approved"):
        return {"decision":"HOLD","reason":"PRICING_NOT_APPROVED"}
    if approval.get("decision")!="APPROVE" or not approval.get("human_approver"):
        return {"decision":"HUMAN_GATE","reason":"CUSTOMER_RELEASE_APPROVAL_REQUIRED"}

    out=json.loads(json.dumps(project))
    out["proposal"]["release_status"]="APPROVED_FOR_CUSTOMER_RELEASE"
    out["quotation"]["customer_release"]="APPROVED_BY_HUMAN"
    out["workspace"]["checklist"]["customer_release_human_approved"]=True
    out["workspace"]["state"]="READY_FOR_CUSTOMER_REVIEW"
    return out

def record_customer_acceptance(project: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    if project.get("workspace",{}).get("state")!="READY_FOR_CUSTOMER_REVIEW":
        return {"decision":"HOLD","reason":"CUSTOMER_RELEASE_NOT_READY"}
    if not evidence.get("evidence_ref") or evidence.get("accepted") is not True:
        return {"decision":"HOLD","reason":"CUSTOMER_ACCEPTANCE_EVIDENCE_REQUIRED"}

    out=json.loads(json.dumps(project))
    out["workspace"]["checklist"]["customer_acceptance_evidence"]=True
    out["workspace"]["state"]="READY_FOR_DELIVERY_PREP"
    out["customer_acceptance_evidence"]=evidence["evidence_ref"]
    return out

def delivery_manifest(project: dict[str, Any]) -> dict[str, Any]:
    if project.get("workspace",{}).get("state")!="READY_FOR_DELIVERY_PREP":
        return {"decision":"HOLD","reason":"DELIVERY_NOT_READY"}
    return {
        "decision":"ALLOW",
        "schema":"ld.delivery-manifest/1",
        "project_id":project["project_id"],
        "state":"PREVIEW_DELIVERY_READY",
        "domain":"CLIENT_OWNED_OR_CLIENT_AUTHORIZED",
        "payment":"DISABLED",
        "production":"LOCKED",
        "production_publish":"HUMAN_ONLY",
        "artifact_digest":_digest({
            "project_id":project["project_id"],
            "onboarding_digest":project["workspace"]["onboarding_digest"],
            "quotation_amount":project["quotation"]["amount"],
        }),
    }
