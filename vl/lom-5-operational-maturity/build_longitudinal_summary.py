from __future__ import annotations

import argparse
import json
from pathlib import Path

from multi_project_evidence import evaluate_registry

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default=str(HERE / "maturity-evidence-registry.json"))
    parser.add_argument("--output", default=str(HERE / "longitudinal-summary.json"))
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()

    registry = json.loads(Path(args.registry).read_text())
    summary = evaluate_registry(registry)
    Path(args.output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))

    if args.require_pass and summary["status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
