from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_canary import validate_canary


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve LOM VPS live-canary evidence against the canonical contract.")
    parser.add_argument("--contract", default="vps-canary-contract.json")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    contract = json.loads(Path(args.contract).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    resolution = validate_canary(contract, evidence)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(resolution, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": resolution.get("status"),
        "reason": resolution.get("reason"),
        "live_vps_verified": resolution.get("live_vps_verified"),
        "activation_status": resolution.get("activation_status"),
        "output": str(output),
    }, sort_keys=True))
    return 0 if resolution.get("status") == "PASS" and resolution.get("live_vps_verified") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
