from __future__ import annotations

from html import escape
from hashlib import sha256
import json
from typing import Any

REQUIRED_COMMON = [
    "business_name",
    "vertical",
    "whatsapp",
    "headline",
    "cta_label",
]

VERTICAL_REQUIRED = {
    "cafe": ["items"],
    "homestay": ["rooms"],
    "tutor": ["programs"],
}

DESIGN_DENSITIES = {"sparse", "balanced", "dense"}
HEADLINE_SCALES = {"compact", "standard", "large"}
DESIGN_STYLE_HINTS = {
    "minimal", "editorial", "premium", "corporate", "friendly",
    "bold", "clean", "warm", "modern", "classic",
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def validate_onboarding(data: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in REQUIRED_COMMON if not data.get(k)]
    vertical = data.get("vertical")
    if vertical not in VERTICAL_REQUIRED:
        return {"decision": "HOLD", "reason": "UNSUPPORTED_VERTICAL"}
    for key in VERTICAL_REQUIRED[vertical]:
        if not isinstance(data.get(key), list) or not data[key]:
            missing.append(key)
    if missing:
        return {"decision": "HOLD", "reason": "ONBOARDING_INCOMPLETE", "missing": sorted(set(missing))}
    if not str(data["whatsapp"]).replace("+","").replace("-","").replace(" ","").isdigit():
        return {"decision": "HOLD", "reason": "WHATSAPP_INVALID"}
    return {"decision": "ALLOW", "digest": _digest(data)}

def _cards(items: list[dict[str, Any]], title_key: str, meta_key: str) -> str:
    blocks=[]
    for item in items:
        title=escape(str(item.get(title_key,"")))
        meta=escape(str(item.get(meta_key,"")))
        desc=escape(str(item.get("description","")))
        blocks.append(f"<article class='card'><h3>{title}</h3><p class='meta'>{meta}</p><p>{desc}</p></article>")
    return "\n".join(blocks)

def _normalize_design_signals(signals: Any) -> dict[str, Any]:
    if not isinstance(signals, dict):
        signals = {}

    density = str(signals.get("layout_density", "balanced")).strip().lower()
    if density not in DESIGN_DENSITIES:
        density = "balanced"

    headline_scale = str(signals.get("headline_scale", "standard")).strip().lower()
    if headline_scale not in HEADLINE_SCALES:
        headline_scale = "standard"

    style_hints = signals.get("style_hints", [])
    normalized_hints: list[str] = []
    if isinstance(style_hints, list):
        for hint in style_hints[:8]:
            key = str(hint).strip().lower()
            if key in DESIGN_STYLE_HINTS and key not in normalized_hints:
                normalized_hints.append(key)

    return {
        "layout_density": density,
        "headline_scale": headline_scale,
        "style_hints": normalized_hints,
    }

def _design_tokens(signals: dict[str, Any]) -> dict[str, str]:
    density = signals["layout_density"]
    density_tokens = {
        "dense": {"main_padding": "18px", "hero_padding": "36px 0 20px", "gap": "10px", "card_padding": "14px"},
        "balanced": {"main_padding": "24px", "hero_padding": "56px 0 28px", "gap": "16px", "card_padding": "18px"},
        "sparse": {"main_padding": "32px", "hero_padding": "76px 0 38px", "gap": "24px", "card_padding": "24px"},
    }[density]

    headline_size = {
        "compact": "clamp(30px,5vw,56px)",
        "standard": "clamp(36px,7vw,72px)",
        "large": "clamp(44px,9vw,92px)",
    }[signals["headline_scale"]]

    hints = set(signals["style_hints"])
    radius = "16px"
    if "minimal" in hints or "bold" in hints:
        radius = "8px"
    elif "premium" in hints or "warm" in hints:
        radius = "20px"
    elif "classic" in hints:
        radius = "12px"

    return {
        **density_tokens,
        "headline_size": headline_size,
        "radius": radius,
    }

def render_preview(data: dict[str, Any], design_signals: dict[str, Any] | None = None) -> dict[str, Any]:
    v=validate_onboarding(data)
    if v["decision"]!="ALLOW":
        return v

    vertical=data["vertical"]
    if vertical=="cafe":
        section_title="Menu Pilihan"
        cards=_cards(data["items"],"name","price")
    elif vertical=="homestay":
        section_title="Bilik & Pakej"
        cards=_cards(data["rooms"],"name","price")
    else:
        section_title="Program Pembelajaran"
        cards=_cards(data["programs"],"name","price")

    business=escape(data["business_name"])
    headline=escape(data["headline"])
    cta=escape(data["cta_label"])
    whatsapp=escape(data["whatsapp"])
    address=escape(data.get("address",""))
    social=escape(data.get("social_url",""))
    maps=escape(data.get("maps_url",""))

    normalized_design=_normalize_design_signals(design_signals)
    tokens=_design_tokens(normalized_design)

    html=f"""<!doctype html>
<html lang='ms'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{business}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:0;background:#f7f7f7;color:#171717}}
main{{max-width:960px;margin:auto;padding:{tokens["main_padding"]}}}
.hero{{padding:{tokens["hero_padding"]}}}
h1{{font-size:{tokens["headline_size"]};line-height:1;margin:0 0 18px}}
.cta{{display:inline-block;padding:14px 20px;border-radius:{tokens["radius"]};background:#111;color:#fff;text-decoration:none;font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:{tokens["gap"]}}}
.card{{background:#fff;border:1px solid #e7e7e7;border-radius:{tokens["radius"]};padding:{tokens["card_padding"]}}}
.meta{{font-weight:700}}
footer{{padding:36px 0;color:#555}}
</style>
</head>
<body>
<main>
<section class='hero'>
<p>{escape(vertical.upper())}</p>
<h1>{headline}</h1>
<p>{business}</p>
<a class='cta' href='https://wa.me/{whatsapp}'>{cta}</a>
</section>
<section>
<h2>{section_title}</h2>
<div class='grid'>{cards}</div>
</section>
<footer>
<p>{address}</p>
<p><a href='{maps}'>Google Maps</a> · <a href='{social}'>Social</a></p>
<p>Preview generated by LD Ready Business Kit P0.</p>
</footer>
</main>
</body>
</html>"""

    manifest={
        "schema":"ld.ready-business-preview/1",
        "vertical":vertical,
        "business_name":data["business_name"],
        "onboarding_digest":v["digest"],
        "design_signals":normalized_design,
        "design_digest":_digest(normalized_design),
        "lead_capture":"CONFIG_REQUIRED",
        "payment":"DISABLED",
        "production":"LOCKED",
        "human_approval_required":True,
    }
    return {"decision":"ALLOW","html":html,"manifest":manifest}
