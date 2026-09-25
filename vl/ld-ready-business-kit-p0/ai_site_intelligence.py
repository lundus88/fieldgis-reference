from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlparse

from ready_business_kit import render_preview

SUPPORTED_VERTICALS = {"cafe", "homestay", "tutor"}
DEFAULTS = {
    "cafe": {
        "headline": "Nikmati pilihan terbaik kami dengan lebih mudah.",
        "cta_label": "Hubungi melalui WhatsApp",
        "section_key": "items",
    },
    "homestay": {
        "headline": "Tempah penginapan anda dengan mudah.",
        "cta_label": "Semak melalui WhatsApp",
        "section_key": "rooms",
    },
    "tutor": {
        "headline": "Mulakan pembelajaran yang lebih terarah.",
        "cta_label": "Tanya melalui WhatsApp",
        "section_key": "programs",
    },
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def _clean_text(value: Any, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]

def _infer_vertical(prompt: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit if explicit in SUPPORTED_VERTICALS else None
    p = prompt.lower()
    aliases = {
        "cafe": ("cafe", "café", "coffee", "kopi", "restaurant", "restoran", "food", "f&b"),
        "homestay": ("homestay", "hotel", "room", "bilik", "penginapan", "chalet"),
        "tutor": ("tutor", "tuition", "kelas", "education", "course", "kursus", "academy"),
    }
    matches = [v for v, words in aliases.items() if any(w in p for w in words)]
    return matches[0] if len(matches) == 1 else None

def _safe_http_url(value: Any) -> str | None:
    text = _clean_text(value, 500)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text

def _validate_cards(cards: Any, max_items: int = 50) -> bool:
    if not isinstance(cards, list) or not cards or len(cards) > max_items:
        return False
    return all(isinstance(item, dict) for item in cards)

def compile_prompt_to_sitespec(request: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic P0 contract for Prompt -> SiteSpec.

    This layer intentionally does not call an external model yet. It converts a
    bounded natural-language request plus explicit business facts into a
    machine-readable SiteSpec, failing closed when required facts are absent.
    """
    prompt = _clean_text(request.get("prompt"), 2000)
    if not prompt:
        return {"decision": "HOLD", "reason": "PROMPT_REQUIRED"}

    business_name = _clean_text(request.get("business_name"), 120)
    whatsapp = _clean_text(request.get("whatsapp"), 40)
    if not business_name or not whatsapp:
        return {
            "decision": "HOLD",
            "reason": "BUSINESS_FACTS_REQUIRED",
            "missing": [k for k, v in (("business_name", business_name), ("whatsapp", whatsapp)) if not v],
        }

    vertical = _infer_vertical(prompt, _clean_text(request.get("vertical"), 40) or None)
    if vertical is None:
        return {"decision": "HOLD", "reason": "VERTICAL_UNRESOLVED"}
    if vertical not in SUPPORTED_VERTICALS:
        return {"decision": "HOLD", "reason": "UNSUPPORTED_VERTICAL"}

    cfg = DEFAULTS[vertical]
    section_key = cfg["section_key"]
    cards = request.get(section_key)
    if not _validate_cards(cards):
        return {"decision": "HOLD", "reason": "VERTICAL_CONTENT_INVALID", "missing": [section_key]}

    headline = _clean_text(request.get("headline"), 180) or cfg["headline"]
    cta_label = _clean_text(request.get("cta_label"), 80) or cfg["cta_label"]

    onboarding = {
        "business_name": business_name,
        "vertical": vertical,
        "whatsapp": whatsapp,
        "headline": headline,
        "cta_label": cta_label,
        section_key: cards,
    }
    address = _clean_text(request.get("address"), 500)
    if address:
        onboarding["address"] = address

    for optional in ("maps_url", "social_url"):
        raw = request.get(optional)
        if raw:
            value = _safe_http_url(raw)
            if value is None:
                return {"decision": "HOLD", "reason": "UNSAFE_URL", "field": optional}
            onboarding[optional] = value

    sections = [
        {"type": "hero", "required": True},
        {"type": "vertical_cards", "source": section_key, "required": True},
        {"type": "contact", "required": True},
    ]
    spec = {
        "schema": "ld.ai-site-spec/1",
        "source_mode": "PROMPT",
        "vertical": vertical,
        "business_name": business_name,
        "language": _clean_text(request.get("language"), 20) or "ms",
        "tone": _clean_text(request.get("tone"), 80) or "professional",
        "sections": sections,
        "prompt_digest": _digest({"prompt": prompt}),
        "facts_digest": _digest(onboarding),
        "content_policy": {
            "invent_business_facts": False,
            "copy_third_party_content": False,
            "production_claim": False,
        },
        "authority": {
            "customer_commitment": "HUMAN_ONLY",
            "production_publish": "HUMAN_ONLY",
        },
    }
    return {"decision": "ALLOW", "sitespec": spec, "onboarding": onboarding}

def generate_prompt_preview(request: dict[str, Any]) -> dict[str, Any]:
    compiled = compile_prompt_to_sitespec(request)
    if compiled["decision"] != "ALLOW":
        return compiled
    preview = render_preview(compiled["onboarding"])
    if preview.get("decision") != "ALLOW":
        return preview
    return {
        "decision": "ALLOW",
        "sitespec": compiled["sitespec"],
        "preview_html": preview["html"],
        "preview_manifest": preview["manifest"],
        "production": "LOCKED",
        "human_approval_required": True,
    }
