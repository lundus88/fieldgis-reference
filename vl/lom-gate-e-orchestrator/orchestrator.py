from dataclasses import dataclass, field
from typing import List, Dict, Any

HUMAN_ONLY = {
    "PROTECTED_MAIN_MERGE",
    "PRODUCTION_DEPLOYMENT",
    "PRODUCTION_RELEASE",
    "PRODUCTION_DATA_MUTATION",
    "AUTHORITY_WIDENING",
    "SECURITY_POLICY_WIDENING",
    "CUSTOMER_OUTREACH",
    "BID_SUBMISSION",
    "QUOTATION_PRICING_COMMITMENT",
    "CONTRACT_LEGAL_COMMITMENT",
    "FINANCIAL_COMMITMENT",
}

ALLOWED_STAGES = [
    "OBJECTIVE",
    "PLAN",
    "RISK_GATE",
    "EXECUTE",
    "VALIDATE",
    "REMEDIATE_IF_ALLOWED",
    "REVALIDATE",
    "LEARN",
    "COMPLETE_OR_ESCALATE",
]

@dataclass
class Objective:
    objective_id: str
    requested_actions: List[str]
    evidence_refs: List[str]
    delegated_actions: List[str]
    risk: str = "LOW"
    production: bool = False
    reversible: bool = True
    executor: str = "EXECUTOR"
    validator: str = "VALIDATOR"

@dataclass
class Outcome:
    objective_id: str
    state: str
    stage: str
    reasons: List[str] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)
    learning_record: Dict[str, Any] = field(default_factory=dict)


def orchestrate(obj: Objective, execution_ok: bool = True, validation_ok: bool = True,
                remediation_ok: bool = True, revalidation_ok: bool = True) -> Outcome:
    reasons: List[str] = []

    if not obj.objective_id:
        return Outcome("UNKNOWN", "HOLD", "OBJECTIVE", ["MISSING_OBJECTIVE_ID"])
    if not obj.evidence_refs:
        return Outcome(obj.objective_id, "HOLD", "OBJECTIVE", ["MISSING_CRITICAL_EVIDENCE"])

    for action in obj.requested_actions:
        if action in HUMAN_ONLY:
            return Outcome(obj.objective_id, "ESCALATE", "RISK_GATE", [f"HUMAN_ONLY:{action}"], obj.evidence_refs)
        if action not in obj.delegated_actions:
            return Outcome(obj.objective_id, "HOLD", "RISK_GATE", [f"OUTSIDE_DELEGATION:{action}"], obj.evidence_refs)

    if obj.risk not in {"LOW", "MEDIUM", "HIGH"}:
        return Outcome(obj.objective_id, "HOLD", "RISK_GATE", ["UNKNOWN_RISK_CLASS"], obj.evidence_refs)
    if obj.risk == "HIGH" or obj.production:
        return Outcome(obj.objective_id, "ESCALATE", "RISK_GATE", ["CONSEQUENTIAL_BOUNDARY"], obj.evidence_refs)
    if obj.executor == obj.validator:
        return Outcome(obj.objective_id, "HOLD", "VALIDATE", ["SELF_CERTIFICATION_FORBIDDEN"], obj.evidence_refs)

    if execution_ok and validation_ok:
        return Outcome(
            obj.objective_id,
            "COMPLETE",
            "COMPLETE_OR_ESCALATE",
            evidence_refs=obj.evidence_refs,
            learning_record={"outcome": "VALIDATED_SUCCESS", "policy_change": "PROPOSE_ONLY"},
        )

    if not execution_ok:
        reasons.append("EXECUTION_FAILED")
    if execution_ok and not validation_ok:
        reasons.append("VALIDATION_FAILED")

    if not obj.reversible or obj.risk != "LOW" or obj.production:
        return Outcome(obj.objective_id, "ESCALATE", "REMEDIATE_IF_ALLOWED", reasons + ["REMEDIATION_NOT_ALLOWED"], obj.evidence_refs)

    if not remediation_ok:
        return Outcome(obj.objective_id, "ESCALATE", "REMEDIATE_IF_ALLOWED", reasons + ["REMEDIATION_FAILED"], obj.evidence_refs)

    if not revalidation_ok:
        return Outcome(obj.objective_id, "ESCALATE", "REVALIDATE", reasons + ["REVALIDATION_FAILED"], obj.evidence_refs)

    return Outcome(
        obj.objective_id,
        "COMPLETE",
        "COMPLETE_OR_ESCALATE",
        reasons + ["REMEDIATED_AND_REVALIDATED"],
        obj.evidence_refs,
        {"outcome": "RECOVERED_SUCCESS", "policy_change": "PROPOSE_ONLY"},
    )
