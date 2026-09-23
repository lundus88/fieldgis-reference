from __future__ import annotations

from hashlib import sha256
import json
from math import ceil
from typing import Any

from ready_business_p1 import create_client_project

ALLOWED_SOURCES = {"referral", "organic", "social", "demo", "direct"}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def create_intake_package(
    onboarding: dict[str, Any],
    *,
    package_key: str = "starter",
    acquisition_source: str = "direct",
    contact_consent: bool = False,
) -> dict[str, Any]:
    if acquisition_source not in ALLOWED_SOURCES:
        return {"decision": "HOLD", "reason": "ACQUISITION_SOURCE_UNSUPPORTED"}
    if contact_consent is not True:
        return {"decision": "HOLD", "reason": "CONTACT_CONSENT_REQUIRED"}

    project = create_client_project(onboarding, package_key)
    if project.get("decision") != "ALLOW":
        return project

    return {
        "decision": "ALLOW",
        "schema": "ld.client-intake-package/1",
        "project": project,
        "acquisition": {
            "source": acquisition_source,
            "contact_consent": True,
            "paid_campaign_spend": "NOT_CAPTURED",
        },
        "payment": "DISABLED",
        "production": "LOCKED",
    }

def clone_manifest(intake: dict[str, Any], template_version: str = "ready-business-p2") -> dict[str, Any]:
    if intake.get("decision") != "ALLOW":
        return {"decision": "HOLD", "reason": "INTAKE_NOT_READY"}
    project = intake["project"]
    workspace = project["workspace"]
    tenant_seed = {
        "project_id": project["project_id"],
        "onboarding_digest": workspace["onboarding_digest"],
        "template_version": template_version,
    }
    tenant_id = "LDT-" + _digest(tenant_seed)[:12].upper()
    manifest = {
        "schema": "ld.clone-manifest/1",
        "tenant_id": tenant_id,
        "project_id": project["project_id"],
        "template_version": template_version,
        "vertical": workspace["vertical"],
        "package_key": workspace["package_key"],
        "configuration_source": workspace["onboarding_digest"],
        "features": {
            "one_page_site": True,
            "whatsapp_cta": True,
            "vertical_cards": True,
            "maps_social": True,
            "lead_capture": "CONFIG_REQUIRED",
            "payment": False,
        },
        "domain": {
            "ownership": "CLIENT",
            "binding": "UNBOUND",
        },
        "secrets_embedded": False,
        "credentials": "NOT_EMBEDDED",
        "production": "LOCKED",
        "publish_authority": "HUMAN_ONLY",
    }
    return {"decision": "ALLOW", "manifest": manifest, "manifest_digest": _digest(manifest)}

def plan_delivery(
    projects: list[dict[str, Any]],
    *,
    daily_limit: int,
    concurrent_limit: int,
) -> dict[str, Any]:
    if daily_limit < 1 or concurrent_limit < 1:
        return {"decision": "HOLD", "reason": "CAPACITY_LIMIT_INVALID"}
    if concurrent_limit > daily_limit:
        return {"decision": "HOLD", "reason": "CONCURRENT_LIMIT_EXCEEDS_DAILY_LIMIT"}
    if any(p.get("decision") != "ALLOW" for p in projects):
        return {"decision": "HOLD", "reason": "PROJECT_SET_NOT_READY"}

    assignments=[]
    for i,p in enumerate(projects):
        within_day=i % daily_limit
        assignments.append({
            "project_id":p["project"]["project_id"],
            "day":(i // daily_limit)+1,
            "wave":(within_day // concurrent_limit)+1,
            "slot":(within_day % concurrent_limit)+1,
        })

    total=len(projects)
    days=ceil(total/daily_limit) if total else 0
    waves_per_full_day=ceil(daily_limit/concurrent_limit)
    bottlenecks=[]
    if total > daily_limit:
        bottlenecks.append("MULTI_DAY_QUEUE")
    if concurrent_limit == 1 and total > 1:
        bottlenecks.append("SERIAL_DELIVERY")
    if total == 0:
        bottlenecks.append("NO_PROJECTS")

    return {
        "decision":"ALLOW",
        "schema":"ld.delivery-capacity-plan/1",
        "synthetic_or_planning_only":True,
        "total_projects":total,
        "daily_limit":daily_limit,
        "concurrent_limit":concurrent_limit,
        "estimated_delivery_days":days,
        "waves_per_full_day":waves_per_full_day,
        "bottlenecks":bottlenecks,
        "assignments":assignments,
        "production":"LOCKED",
    }

def simulate_ten_customers(
    base_onboardings: list[dict[str, Any]],
    *,
    daily_limit: int = 3,
    concurrent_limit: int = 1,
) -> dict[str, Any]:
    if not base_onboardings:
        return {"decision":"HOLD","reason":"NO_BASE_FIXTURES"}

    intakes=[]
    clones=[]
    for i in range(10):
        data=json.loads(json.dumps(base_onboardings[i % len(base_onboardings)]))
        data["business_name"]=f"Synthetic Client {i+1:02d} — {data['business_name']}"
        data["whatsapp"]=f"6010000{i+1:04d}"
        intake=create_intake_package(
            data,
            package_key="starter",
            acquisition_source="demo",
            contact_consent=True,
        )
        if intake.get("decision")!="ALLOW":
            return {"decision":"HOLD","reason":"SYNTHETIC_INTAKE_FAILED","index":i}
        clone=clone_manifest(intake)
        if clone.get("decision")!="ALLOW":
            return {"decision":"HOLD","reason":"SYNTHETIC_CLONE_FAILED","index":i}
        intakes.append(intake)
        clones.append(clone)

    capacity=plan_delivery(intakes,daily_limit=daily_limit,concurrent_limit=concurrent_limit)
    ids=[x["project"]["project_id"] for x in intakes]
    tenant_ids=[x["manifest"]["tenant_id"] for x in clones]

    return {
        "decision":"ALLOW",
        "schema":"ld.synthetic-ten-client-report/1",
        "synthetic_only":True,
        "live_customers":False,
        "revenue_evidence":False,
        "payment_transactions":0,
        "production_deployments":0,
        "customer_count":10,
        "unique_project_ids":len(set(ids)),
        "unique_tenant_ids":len(set(tenant_ids)),
        "all_payment_disabled":all(x["payment"]=="DISABLED" for x in intakes),
        "all_production_locked":all(x["production"]=="LOCKED" for x in intakes),
        "capacity_plan":capacity,
        "activation_authorized":False,
    }
