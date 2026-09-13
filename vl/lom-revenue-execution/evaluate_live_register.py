import json
from pathlib import Path

ROOT = Path(__file__).parent
REGISTER = json.loads((ROOT / "live-opportunity-register.json").read_text())


def evaluate(entry):
    status = entry["status"]
    if status == "WATCHLIST":
        return {"id": entry["id"], "decision": "WATCHLIST", "next_best_action": entry["next_action"]}
    if status == "HOLD":
        return {"id": entry["id"], "decision": "HOLD", "next_best_action": entry["next_action"]}
    raise ValueError(f"Unsupported status: {status}")


if __name__ == "__main__":
    result = [evaluate(x) for x in REGISTER["entries"]]
    print(json.dumps(result, indent=2))
