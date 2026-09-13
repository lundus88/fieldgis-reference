import json
from pathlib import Path

ROOT = Path(__file__).parent
QUEUE = json.loads((ROOT / "conversion-queue.json").read_text())


def evaluate(item):
    if item["route"] == "WATCH_FOR_REPEAT":
        return {
            "decision": "WATCHLIST",
            "reason": "Historical market proof or recurring procurement pattern; no active pursuit evidence.",
            "next_best_action": item["next_evidence_action"],
        }

    missing = []
    if item.get("survey_value_rm") is None:
        missing.append("survey_value")
    if item.get("survey_scope") != "CONFIRMED":
        missing.append("survey_scope")
    if item.get("customer_intent") != "CONFIRMED":
        missing.append("customer_intent")
    if item.get("direct_bid_eligibility") in {"UNVERIFIED", "NOT_ESTABLISHED_FOR_SURVEYOR", "UNKNOWN"}:
        missing.append("eligibility")

    if missing:
        return {
            "decision": "HOLD",
            "reason": "Missing conversion evidence: " + ", ".join(missing),
            "next_best_action": item["next_evidence_action"],
        }

    return {
        "decision": "CONTINUE",
        "reason": "Minimum conversion evidence is present; economic scoring still required before ACCELERATE.",
        "next_best_action": "Pass verified opportunity into the P6 economic scorer.",
    }


def main():
    output = {item["id"]: evaluate(item) for item in QUEUE["items"]}
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
