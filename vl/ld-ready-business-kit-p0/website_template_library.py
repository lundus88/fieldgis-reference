from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

SCHEMA = "ld.website-template-library/1"
TEMPLATE_SCHEMA = "ld.website-template/1"

REQUIRED_SECTIONS = {"hero", "trust", "offer", "process", "cta"}
ALLOWED_LANES = {"EXPRESS_24H", "FAST_48H", "STANDARD_3DAY"}
ALLOWED_CAPABILITIES = {
    "WHATSAPP_CTA",
    "LEAD_CAPTURE",
    "ANALYTICS",
    "SEO_BASIC",
    "PORTFOLIO",
    "TESTIMONIALS",
    "FAQ",
    "MAP",
    "PRODUCT_CATALOG",
    "PAYMENT_ADAPTER",
    "QUOTATION",
    "AI_COPY_ASSIST",
}

TEMPLATES: dict[str, dict[str, Any]] = {
    "surveyor-pro": {
        "schema": TEMPLATE_SCHEMA,
        "template_id": "surveyor-pro",
        "name": "Surveyor Pro",
        "vertical": "surveying-geospatial",
        "positioning": "Professional land surveying and geospatial services",
        "visual_style": "technical-premium",
        "delivery_lane": "FAST_48H",
        "sections": ["hero","trust","offer","process","portfolio","faq","cta"],
        "capabilities": ["WHATSAPP_CTA","LEAD_CAPTURE","ANALYTICS","SEO_BASIC","PORTFOLIO","FAQ","AI_COPY_ASSIST"],
        "conversion_goal": "qualified_enquiry",
    },
    "property-land": {
        "schema": TEMPLATE_SCHEMA,
        "template_id": "property-land",
        "name": "Property & Land",
        "vertical": "property-broker",
        "positioning": "Property and land discovery with clear conversion paths",
        "visual_style": "editorial-luxury",
        "delivery_lane": "FAST_48H",
        "sections": ["hero","trust","offer","portfolio","process","faq","cta"],
        "capabilities": ["WHATSAPP_CTA","LEAD_CAPTURE","ANALYTICS","SEO_BASIC","PORTFOLIO","MAP","FAQ","AI_COPY_ASSIST"],
        "conversion_goal": "property_lead",
    },
    "contractor-engineering": {
        "schema": TEMPLATE_SCHEMA,
        "template_id": "contractor-engineering",
        "name": "Contractor & Engineering",
        "vertical": "contractor-engineering",
        "positioning": "Capability, project evidence and quotation-ready enquiries",
        "visual_style": "industrial-clean",
        "delivery_lane": "FAST_48H",
        "sections": ["hero","trust","offer","portfolio","process","testimonials","cta"],
        "capabilities": ["WHATSAPP_CTA","LEAD_CAPTURE","ANALYTICS","SEO_BASIC","PORTFOLIO","TESTIMONIALS","QUOTATION","AI_COPY_ASSIST"],
        "conversion_goal": "quotation_request",
    },
    "sme-corporate": {
        "schema": TEMPLATE_SCHEMA,
        "template_id": "sme-corporate",
        "name": "SME Corporate",
        "vertical": "sme",
        "positioning": "A credible digital front door for small and growing businesses",
        "visual_style": "modern-clean",
        "delivery_lane": "EXPRESS_24H",
        "sections": ["hero","trust","offer","process","testimonials","faq","cta"],
        "capabilities": ["WHATSAPP_CTA","LEAD_CAPTURE","ANALYTICS","SEO_BASIC","TESTIMONIALS","FAQ","AI_COPY_ASSIST"],
        "conversion_goal": "business_enquiry",
    },
    "commerce-launch": {
        "schema": TEMPLATE_SCHEMA,
        "template_id": "commerce-launch",
        "name": "Commerce Launch",
        "vertical": "commerce",
        "positioning": "Fast product discovery and purchase intent",
        "visual_style": "conversion-bold",
        "delivery_lane": "STANDARD_3DAY",
        "sections": ["hero","trust","offer","portfolio","process","faq","cta"],
        "capabilities": ["WHATSAPP_CTA","LEAD_CAPTURE","ANALYTICS","SEO_BASIC","PRODUCT_CATALOG","PAYMENT_ADAPTER","FAQ","AI_COPY_ASSIST"],
        "conversion_goal": "purchase_intent",
    },
    "premium-professional": {
        "schema": TEMPLATE_SCHEMA,
        "template_id": "premium-professional",
        "name": "Premium Professional",
        "vertical": "professional-services",
        "positioning": "Authority-led presentation for consultants and professional services",
        "visual_style": "minimal-premium",
        "delivery_lane": "EXPRESS_24H",
        "sections": ["hero","trust","offer","process","testimonials","faq","cta"],
        "capabilities": ["WHATSAPP_CTA","LEAD_CAPTURE","ANALYTICS","SEO_BASIC","TESTIMONIALS","FAQ","AI_COPY_ASSIST"],
        "conversion_goal": "consultation_enquiry",
    },
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def validate_template(template: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(template, dict):
        return {"decision":"HOLD","reason":"TEMPLATE_REQUIRED"}
    required = ["schema","template_id","name","vertical","positioning","visual_style","delivery_lane","sections","capabilities","conversion_goal"]
    missing = [k for k in required if not template.get(k)]
    if missing:
        return {"decision":"HOLD","reason":"TEMPLATE_INCOMPLETE","missing":sorted(missing)}
    if template["schema"] != TEMPLATE_SCHEMA:
        return {"decision":"HOLD","reason":"TEMPLATE_SCHEMA_UNSUPPORTED"}
    if template["delivery_lane"] not in ALLOWED_LANES:
        return {"decision":"HOLD","reason":"DELIVERY_LANE_UNSUPPORTED"}
    sections = template.get("sections")
    if not isinstance(sections, list) or not REQUIRED_SECTIONS.issubset(set(sections)):
        return {"decision":"HOLD","reason":"REQUIRED_CONVERSION_SECTIONS_MISSING"}
    capabilities = set(template.get("capabilities") or [])
    unknown = sorted(capabilities - ALLOWED_CAPABILITIES)
    if unknown:
        return {"decision":"HOLD","reason":"TEMPLATE_CAPABILITY_UNKNOWN","unknown":unknown}
    if "WHATSAPP_CTA" not in capabilities or "LEAD_CAPTURE" not in capabilities:
        return {"decision":"HOLD","reason":"CONVERSION_PATH_REQUIRED"}
    return {"decision":"ALLOW","digest":_digest(template)}

def library_manifest() -> dict[str, Any]:
    entries=[]
    for template_id in sorted(TEMPLATES):
        template=TEMPLATES[template_id]
        verdict=validate_template(template)
        if verdict["decision"]!="ALLOW":
            return verdict
        entries.append({
            "template_id":template_id,
            "name":template["name"],
            "vertical":template["vertical"],
            "visual_style":template["visual_style"],
            "delivery_lane":template["delivery_lane"],
            "conversion_goal":template["conversion_goal"],
            "template_digest":verdict["digest"],
        })
    return {
        "decision":"ALLOW",
        "schema":SCHEMA,
        "templates":entries,
        "renderer_owner":"LD_READY_BUSINESS_KIT",
        "business_engine_owner":"LUNDUS_BUSINESS_ENGINE",
        "production":"LOCKED",
        "customer_commitment":"HUMAN_ONLY",
        "pricing":"HUMAN_ONLY",
        "promise_policy":"delivery lanes are eligibility targets, not unconditional guarantees",
        "library_digest":_digest(entries),
    }

def resolve_template(template_id: str) -> dict[str, Any]:
    template=TEMPLATES.get(template_id)
    if template is None:
        return {"decision":"HOLD","reason":"TEMPLATE_NOT_FOUND","template_id":template_id}
    verdict=validate_template(template)
    if verdict["decision"]!="ALLOW":
        return verdict
    return {
        "decision":"ALLOW",
        "template":template,
        "template_digest":verdict["digest"],
        "composition":{
            "renderer":"LD_READY_BUSINESS_KIT",
            "commercial_lifecycle":"LUNDUS_BUSINESS_ENGINE",
            "lead_owner":"LUNDUSLEAD",
            "production":"LOCKED",
            "human_approval_required":True,
        },
    }

def recommend_lane(template_id: str, inputs_ready: bool, scope_locked: bool) -> dict[str, Any]:
    resolved=resolve_template(template_id)
    if resolved["decision"]!="ALLOW":
        return resolved
    lane=resolved["template"]["delivery_lane"]
    if not inputs_ready:
        return {"decision":"HOLD","reason":"CUSTOMER_INPUTS_INCOMPLETE","clock":"PAUSED"}
    if not scope_locked:
        return {"decision":"HOLD","reason":"SCOPE_NOT_LOCKED","clock":"PAUSED"}
    return {
        "decision":"ALLOW",
        "delivery_lane":lane,
        "commitment":"TARGET_ONLY",
        "production":"LOCKED",
        "human_quote_and_commitment_required":True,
    }
