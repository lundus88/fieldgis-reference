"""Governance doctrine consistency guard for LOM Virtual World."""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List

ROOT=Path(__file__).resolve().parent

FILES={
    "charter": ROOT/"FOUNDING_CHARTER_V1.md",
    "world": ROOT/"WORLD_OPERATING_MODEL_V1.md",
    "architecture": ROOT/"ARCHITECTURE_V1.md",
}

FORBIDDEN=[
    "bounded platform voting",
    "Platform governance voting where appropriate",
]

def load_docs() -> Dict[str,str]:
    return {k:p.read_text(encoding="utf-8") for k,p in FILES.items()}

def validate_governance_docs(docs: Dict[str,str]) -> List[str]:
    errors=[]
    all_text="\n".join(docs.values())

    if "Founder-Led Constitutional Platform" not in docs["charter"]:
        errors.append("CHARTER_FOUNDER_LED_MODEL_MISSING")
    if "Founder-Led Constitutional Platform" not in docs["world"]:
        errors.append("WORLD_FOUNDER_LED_MODEL_MISSING")
    if "There are **no elections or binding member votes that determine governing power**" not in docs["charter"]:
        errors.append("NO_ELECTIONS_RULE_MISSING")
    if "no person or AI may bypass the active Charter" not in docs["charter"] and "No person or AI may bypass the active Charter" not in docs["charter"]:
        errors.append("RULES_BOUND_AUTHORITY_MISSING")
    if "appoint itself as successor" not in all_text:
        errors.append("AI_SELF_SUCCESSION_BOUNDARY_MISSING")
    if "ADVANCED_SOCIETY_FUNDAMENTALS_V1.md" not in all_text:
        errors.append("TWELVE_FUNDAMENTALS_REFERENCE_MISSING")
    if "BEST-OF-WORLD ARCHITECTURE" not in docs["charter"]:
        errors.append("BEST_OF_WORLD_ARCHITECTURE_MISSING")

    for phrase in FORBIDDEN:
        if phrase in all_text:
            errors.append(f"FORBIDDEN_GOVERNANCE_PHRASE:{phrase}")
    return errors
