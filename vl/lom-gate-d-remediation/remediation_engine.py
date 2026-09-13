import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT / "remediation-policy.json").read_text())

RISK_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def decide(case):
    action = case.get("action")
    if not action:
        return {"decision": "HOLD", "reason": "UNKNOWN_AUTHORITY"}

    if action in POLICY["human_only_actions"]:
        return {"decision": "ESCALATE", "reason": "HUMAN_ONLY"}

    if case.get("environment") != "NON_PRODUCTION":
        return {"decision": "ESCALATE", "reason": "PRODUCTION_BOUNDARY"}

    if not case.get("reversible", False):
        return {"decision": "HOLD", "reason": "NOT_REVERSIBLE"}

    if not case.get("evidence"):
        return {"decision": "HOLD", "reason": "EVIDENCE_REQUIRED"}

    risk = case.get("risk")
    if risk not in RISK_ORDER:
        return {"decision": "HOLD", "reason": "UNKNOWN_RISK"}
    if RISK_ORDER[risk] > RISK_ORDER[POLICY["allowed_conditions"]["max_risk"]]:
        return {"decision": "ESCALATE", "reason": "RISK_THRESHOLD_EXCEEDED"}

    attempts = int(case.get("attempts", 0))
    if attempts >= POLICY["allowed_conditions"]["max_attempts"]:
        return {"decision": "HOLD", "reason": "ATTEMPT_LIMIT_REACHED"}

    if case.get("executor") and case.get("validator") and case["executor"] == case["validator"]:
        return {"decision": "HOLD", "reason": "SELF_CERTIFICATION_FORBIDDEN"}

    return {
        "decision": "REMEDIATE",
        "reason": "BOUNDED_REMEDIATION_ALLOWED",
        "next": "INDEPENDENT_REVALIDATION"
    }


def finalize(remediation_result, validation):
    if remediation_result != "SUCCESS":
        return {"outcome": "HOLD", "reason": "REMEDIATION_FAILED"}
    if validation != "PASS":
        return {"outcome": "FAILED_VALIDATION", "reason": "INDEPENDENT_REVALIDATION_FAILED"}
    return {"outcome": "RECOVERED", "reason": "VALIDATED_RECOVERY"}


if __name__ == "__main__":
    demo = {
        "action": "NON_PRODUCTION_REVERSIBLE_ACTION",
        "environment": "NON_PRODUCTION",
        "reversible": True,
        "risk": "LOW",
        "evidence": ["test-failure"],
        "attempts": 0,
        "executor": "EXECUTOR",
        "validator": "VALIDATOR"
    }
    print(decide(demo))
