from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

HUMAN_ONLY_ACTIONS = {
    "PRODUCTION_RELEASE","PRODUCTION_DEPLOY","PRODUCTION_DATA_MUTATION",
    "PROTECTED_MAIN_MERGE","AUTHORITY_WIDENING","FINANCIAL_COMMITMENT",
    "LEGAL_COMMITMENT","CONTRACT_COMMITMENT","CUSTOMER_COMMITMENT",
    "PRICING_COMMITMENT","BID_SUBMISSION",
}

BAD_EVIDENCE = {"MISSING","STALE","CONTRADICTORY","UNVERIFIED","UNKNOWN"}

@dataclass(frozen=True)
class CognitiveInput:
    objective_id: str
    project_id: str
    evidence_status: str
    evidence_refs: List[str]
    authority_class: str
    risk: str
    reversible: bool
    environment: str
    confidence: Optional[float] = None
    options: List[Dict[str, Any]] = field(default_factory=list)
    precedent_refs: List[str] = field(default_factory=list)
    blast_radius: str = "UNKNOWN"

def _hold(reason: str, x: CognitiveInput) -> Dict[str, Any]:
    return {
        "schema": "lom.cognitive-decision-package/1",
        "objective_id": x.objective_id,
        "project_id": x.project_id,
        "decision": "HOLD",
        "reason": reason,
        "execution_authority": "NONE",
        "next_best_action": "RESTORE_EVIDENCE_OR_REQUEST_HUMAN_REVIEW",
        "human_decision_required": True,
        "evidence_refs": list(x.evidence_refs),
        "precedent_refs": list(x.precedent_refs),
        "blast_radius": x.blast_radius,
        "execution_performed": False,
    }

def evaluate(x: CognitiveInput) -> Dict[str, Any]:
    if not x.objective_id or not x.project_id:
        return _hold("IDENTITY_REQUIRED", x)
    if not x.evidence_refs:
        return _hold("EVIDENCE_REQUIRED", x)
    if x.evidence_status in BAD_EVIDENCE:
        return _hold(f"EVIDENCE_{x.evidence_status}", x)
    if x.authority_class in HUMAN_ONLY_ACTIONS:
        out = _hold("HUMAN_ONLY_AUTHORITY", x)
        out["next_best_action"] = "PREPARE_HUMAN_DECISION_PACKAGE"
        return out
    if x.environment == "PRODUCTION":
        out = _hold("PRODUCTION_HUMAN_ONLY", x)
        out["next_best_action"] = "PREPARE_HUMAN_DECISION_PACKAGE"
        return out
    if x.risk not in {"LOW","MEDIUM","HIGH","CRITICAL"}:
        return _hold("UNKNOWN_RISK", x)
    if x.risk in {"HIGH","CRITICAL"}:
        out = _hold("RISK_REQUIRES_HUMAN_REVIEW", x)
        out["next_best_action"] = "PREPARE_HUMAN_DECISION_PACKAGE"
        return out
    if x.confidence is None or not (0.0 <= x.confidence <= 1.0):
        return _hold("CALIBRATED_CONFIDENCE_REQUIRED", x)
    if not x.options:
        return _hold("DECISION_OPTIONS_REQUIRED", x)

    ranked = sorted(
        x.options,
        key=lambda o: (
            float(o.get("expected_value", 0.0)),
            -float(o.get("risk_score", 1.0)),
            -float(o.get("cost_score", 1.0)),
        ),
        reverse=True,
    )
    selected = ranked[0]
    allowed = x.reversible and x.risk == "LOW"
    return {
        "schema": "lom.cognitive-decision-package/1",
        "objective_id": x.objective_id,
        "project_id": x.project_id,
        "decision": "PREPARE_PR" if allowed else "HUMAN_REVIEW",
        "reason": "LOW_RISK_REVERSIBLE_EVIDENCE_BOUND" if allowed else "REVIEW_REQUIRED",
        "selected_option": selected.get("id"),
        "option_count": len(ranked),
        "counterfactuals": [
            {
                "option_id": o.get("id"),
                "expected_value": o.get("expected_value"),
                "risk_score": o.get("risk_score"),
                "cost_score": o.get("cost_score"),
            } for o in ranked
        ],
        "calibrated_confidence": x.confidence,
        "evidence_status": x.evidence_status,
        "evidence_refs": list(x.evidence_refs),
        "precedent_refs": list(x.precedent_refs),
        "blast_radius": x.blast_radius,
        "execution_authority": "PREPARE_PR" if allowed else "NONE",
        "human_decision_required": not allowed,
        "learning_disposition": "RECORD_AND_PROPOSE_ONLY",
        "self_approval": "FORBIDDEN",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "execution_performed": False,
    }
