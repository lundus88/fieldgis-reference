from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SPEC = json.loads((HERE / "spec.json").read_text(encoding="utf-8"))
OUT = HERE / "execution-result.json"

def run(cmd: list[str]) -> dict:
    started = time.monotonic()
    completed = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    elapsed = time.monotonic() - started
    return {
        "cmd": cmd,
        "returncode": completed.returncode,
        "elapsed_seconds": round(elapsed, 6),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }

def main() -> int:
    started = time.monotonic()
    sha = os.environ.get("GITHUB_SHA", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if len(sha) not in {40, 64}:
        raise SystemExit("GITHUB_SHA_REQUIRED")
    if not run_id:
        raise SystemExit("GITHUB_RUN_ID_REQUIRED")

    checks = [
        run([sys.executable, "vl/lom-canonical-compliance/validate_canonical_chain.py"]),
        run([
            sys.executable, "-m", "unittest", "-v",
            "vl/lom-5-operational-maturity/test_evidence_capture.py",
        ]),
    ]

    result = {
        "schema": "lom.golden-workflow-execution/2",
        "golden_run_id": SPEC["run_id"],
        "project_id": SPEC["project_id"],
        "github_sha": sha,
        "github_run_id": run_id,
        "attempts": 1,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "estimated_model_tool_cost": 0.0,
        "model_or_external_api_calls": 0,
        "budget_overrun": False,
        "authority_expansion_incident": False,
        "fabricated_pass_incident": False,
        "production_approval": False,
        "builder_self_certified": False,
        "checks": checks,
        "execution_passed": all(c["returncode"] == 0 for c in checks),
        "production_locked": True,
        "autonomous_ceiling": "PREPARE_PR",
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["execution_passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
