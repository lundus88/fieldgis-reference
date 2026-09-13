import json
from datetime import date
from pathlib import Path


HOLD = "HOLD"
DIRECT = "DIRECT_MATCH"
CONDITIONAL = "CONDITIONAL_MATCH"
PARTNER = "PARTNER_MATCH"


def _parse_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def load_json(name):
    return json.loads((Path(__file__).parent / name).read_text(encoding="utf-8"))


def infer_candidate_codes(text, codebook=None):
    """Return candidate SSB codes from tender wording.

    Candidate codes are discovery hints only and never confirm tender scope.
    """
    if codebook is None:
        codebook = load_json("service-codes.json")
    haystack = (text or "").lower()
    matches = []
    for entry in codebook["codes"]:
        if any(keyword.lower() in haystack for keyword in entry.get("keywords", [])):
            matches.append(entry["code"])
    return sorted(set(matches))


def _current_registration_codes(firm, as_of):
    current = set()
    for item in firm.get("procurement_codes", []):
        valid_until = _parse_date(item.get("valid_until"))
        if item.get("evidence_state") == "CURRENT" and valid_until and valid_until >= as_of:
            current.add((item.get("scheme", "").upper(), item.get("code", "").upper()))
    return current


def evaluate_firm(tender, firm, as_of=None):
    if as_of is None:
        as_of = date.today()

    reasons = []
    licence = firm.get("ssb_license", {})
    valid_until = _parse_date(licence.get("valid_until"))

    if valid_until is None or valid_until < as_of:
        return {"firm": firm.get("id"), "decision": HOLD, "reasons": ["SSB_LICENCE_NOT_CURRENT"]}

    if licence.get("new_work_authority") != "FULL":
        return {"firm": firm.get("id"), "decision": HOLD, "reasons": ["NEW_WORK_AUTHORITY_NOT_FULL"]}

    required_ssb = set(tender.get("required_ssb_codes", []))
    held_ssb = set(firm.get("ssb_disciplines", firm.get("ssb_disciplines_evidenced", [])))
    missing_ssb = sorted(required_ssb - held_ssb)
    if missing_ssb:
        overlap = required_ssb & held_ssb
        decision = PARTNER if overlap else HOLD
        return {
            "firm": firm.get("id"),
            "decision": decision,
            "reasons": ["MANDATORY_SSB_CODE_NOT_EVIDENCED"],
            "missing_ssb_codes": missing_ssb,
        }

    required_proc = {
        (item.get("scheme", "").upper(), item.get("code", "").upper())
        for item in tender.get("required_procurement_codes", [])
    }
    current_proc = _current_registration_codes(firm, as_of)
    missing_proc = sorted(required_proc - current_proc)
    if missing_proc:
        return {
            "firm": firm.get("id"),
            "decision": CONDITIONAL,
            "reasons": ["MANDATORY_PROCUREMENT_CODE_NOT_EVIDENCED_CURRENT"],
            "missing_procurement_codes": [f"{scheme}:{code}" for scheme, code in missing_proc],
        }

    if not tender.get("scope_confirmed", False):
        reasons.append("TENDER_SCOPE_NOT_CONFIRMED")
        return {"firm": firm.get("id"), "decision": CONDITIONAL, "reasons": reasons}

    return {"firm": firm.get("id"), "decision": DIRECT, "reasons": ["CURRENT_EVIDENCE_MATCHES_CONFIRMED_REQUIREMENTS"]}


def analyze_tender(title, description, required_procurement_codes=None, scope_confirmed=False, registry=None, codebook=None, as_of=None):
    if registry is None:
        registry = load_json("firm-registry.json")
    if codebook is None:
        codebook = load_json("service-codes.json")
    text = f"{title or ''} {description or ''}".strip()
    candidates = infer_candidate_codes(text, codebook)
    tender = {
        "required_ssb_codes": candidates if scope_confirmed else [],
        "candidate_ssb_codes": candidates,
        "required_procurement_codes": required_procurement_codes or [],
        "scope_confirmed": scope_confirmed,
    }
    return {
        "candidate_ssb_codes": candidates,
        "scope_confirmed": scope_confirmed,
        "warning": "KEYWORD_MATCH_IS_NOT_CONFIRMED_SCOPE" if candidates and not scope_confirmed else None,
        "firm_matches": [evaluate_firm(tender, firm, as_of=as_of) for firm in registry["firms"]],
    }
