import json
from pathlib import Path

ROOT = Path(__file__).parent
POLICY = json.loads((ROOT / "revenue-policy.json").read_text())


def score(opportunity):
    if not opportunity.get("evidence_refs"):
        return {"decision": "HOLD", "score": None, "reason": "Missing evidence", "next_best_action": "Restore trustworthy evidence before pursuit."}
    if opportunity.get("evidence_status") == "STALE":
        return {"decision": "REVIEW", "score": None, "reason": "Stale evidence", "next_best_action": "Refresh evidence before economic decision."}

    total = 0.0
    for key, weight in POLICY["score_dimensions"].items():
        value = opportunity.get(key)
        if value is None:
            return {"decision": "HOLD", "score": None, "reason": f"Missing score input: {key}", "next_best_action": "Complete missing economic evidence."}
        if not 0 <= value <= 100:
            raise ValueError(f"{key} must be between 0 and 100")
        total += value * weight

    final_score = round(total, 2)
    bands = POLICY["decision_bands"]
    if final_score >= bands["ACCELERATE"]:
        decision = "ACCELERATE"
        action = "Prepare a Director decision package for priority pursuit."
    elif final_score >= bands["CONTINUE"]:
        decision = "CONTINUE"
        action = "Continue evidence-backed pursuit within delegated scope."
    elif final_score >= bands["HOLD"]:
        decision = "HOLD"
        action = "Hold commitment and improve economics, evidence, or risk profile."
    else:
        decision = "STOP"
        action = "Recommend stopping further effort unless new evidence materially changes the case."

    return {"decision": decision, "score": final_score, "reason": "Evidence-backed economic score", "next_best_action": action}


if __name__ == "__main__":
    sample = {
        "revenue_potential": 80,
        "probability_of_success": 70,
        "strategic_value": 80,
        "urgency": 60,
        "delivery_risk": 30,
        "effort_cost": 40,
        "evidence_status": "FRESH",
        "evidence_refs": ["sample-evidence"]
    }
    print(json.dumps(score(sample), indent=2))
