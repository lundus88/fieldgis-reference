import json
from pathlib import Path

DIRECT_TENDER = "DIRECT_TENDER"
CONFIRMED_CLIENT_NEED = "CONFIRMED_CLIENT_NEED"
POTENTIAL_SERVICE_NEED = "POTENTIAL_SERVICE_NEED"
NO_RELEVANT_SIGNAL = "NO_RELEVANT_SIGNAL"

TENDER_SOURCES = {"TENDER", "QUOTATION", "RFQ", "RFP"}
CLIENT_SOURCES = {"CLIENT", "CONTRACTOR", "DEVELOPER", "CONSULTANT", "PROJECT", "OWNER", "AGENCY"}

DOWNSTREAM_INFRASTRUCTURE_SIGNALS = [
    "pemasangan paip",
    "kerja-kerja paip",
    "paip air",
    "water pipe installation",
    "pipe installation",
    "pipeline works",
    "road construction",
    "pembinaan jalan",
    "slope stabilisation",
    "slope stabilization",
    "earthworks",
    "kerja tanah",
]


def load_json(name):
    return json.loads((Path(__file__).parent / name).read_text(encoding="utf-8"))


def candidate_ssb_codes(text, codebook=None):
    if codebook is None:
        codebook = load_json("service-codes.json")
    haystack = (text or "").lower()
    found = []
    for entry in codebook["codes"]:
        if any(k.lower() in haystack for k in entry.get("keywords", [])):
            found.append(entry["code"])
    return sorted(set(found))


def service_categories(text, watchbook=None):
    if watchbook is None:
        watchbook = load_json("service-watch.json")
    haystack = (text or "").lower()
    found = []
    for entry in watchbook["service_categories"]:
        if any(k.lower() in haystack for k in entry.get("keywords", [])):
            found.append(entry["id"])
    return sorted(set(found))


def procurement_code_signals(text, watchbook=None):
    if watchbook is None:
        watchbook = load_json("service-watch.json")
    haystack = (text or "").lower()
    found = []
    for entry in watchbook.get("procurement_service_codes", []):
        if entry["code"].lower() in haystack:
            found.append({"scheme": entry["scheme"], "code": entry["code"], "description": entry["description"]})
    return found


def downstream_infrastructure_signals(text):
    haystack = (text or "").lower()
    return sorted({signal for signal in DOWNSTREAM_INFRASTRUCTURE_SIGNALS if signal in haystack})


def analyze(title, description, source_type="OTHER", scope_confirmed=False, codebook=None, watchbook=None):
    text = f"{title or ''} {description or ''}".strip()
    source_type = (source_type or "OTHER").upper()
    codes = candidate_ssb_codes(text, codebook)
    categories = service_categories(text, watchbook)
    procurement = procurement_code_signals(text, watchbook)
    downstream = downstream_infrastructure_signals(text)
    has_explicit_signal = bool(codes or categories or procurement)

    if has_explicit_signal and scope_confirmed and source_type in TENDER_SOURCES:
        result = DIRECT_TENDER
        evidence = "EXPLICIT_SCOPE_CONFIRMED"
        warning = None
        next_action = "Capture deadline and exact service scope for Director review."
    elif has_explicit_signal and scope_confirmed and source_type in CLIENT_SOURCES:
        result = CONFIRMED_CLIENT_NEED
        evidence = "EXPLICIT_CLIENT_NEED_CONFIRMED"
        warning = None
        next_action = "Capture the requirement and evidence source for Director review."
    elif has_explicit_signal:
        result = POTENTIAL_SERVICE_NEED
        evidence = "KEYWORD_SIGNAL_ONLY"
        warning = "KEYWORD_MATCH_IS_NOT_CONFIRMED_SCOPE"
        next_action = "Verify source evidence for explicit survey/mapping scope."
    elif downstream:
        result = POTENTIAL_SERVICE_NEED
        evidence = "DOWNSTREAM_INFRASTRUCTURE_SIGNAL_ONLY"
        warning = "INFRASTRUCTURE_SIGNAL_IS_NOT_CONFIRMED_SURVEY_SCOPE"
        next_action = "Review source documents for explicit survey, setting-out, as-built, mapping, GIS, control or route-survey scope."
    else:
        result = NO_RELEVANT_SIGNAL
        evidence = "NO_SUPPORTED_SERVICE_SIGNAL"
        warning = None
        next_action = "No survey/mapping follow-up unless new evidence appears."

    return {
        "source_type": source_type,
        "opportunity_class": result,
        "service_categories": categories,
        "candidate_ssb_codes": codes,
        "candidate_procurement_service_codes": procurement,
        "downstream_infrastructure_signals": downstream,
        "scope_confirmed": bool(scope_confirmed),
        "evidence_state": evidence,
        "warning": warning,
        "next_best_action": next_action,
    }
