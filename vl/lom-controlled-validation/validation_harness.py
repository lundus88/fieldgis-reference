from dataclasses import dataclass, asdict
from typing import Callable, Dict, List
import json

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lom-autonomous-org"))

from org_runtime import route, learn  # noqa: E402


@dataclass
class ValidationRecord:
    scenario: str
    expected: str
    actual: str
    passed: bool
    evidence: Dict[str, object]


def validate_route(
    scenario: str,
    expected: str,
    action: str,
    evidence_status: str,
    risk: str,
    reversible: bool,
    production: bool,
) -> ValidationRecord:
    result = route(action, evidence_status, risk, reversible, production)
    actual = result["decision"]
    return ValidationRecord(
        scenario=scenario,
        expected=expected,
        actual=actual,
        passed=actual == expected,
        evidence={
            "action": action,
            "evidence_status": evidence_status,
            "risk": risk,
            "reversible": reversible,
            "production": production,
            "reason": result.get("reason"),
        },
    )


def run() -> List[ValidationRecord]:
    records = [
        validate_route(
            "safe delegated action",
            "DELEGATE",
            "RUN_TEST",
            "COMPLETE",
            "LOW",
            True,
            False,
        ),
        validate_route(
            "unknown authority fails closed",
            "HOLD",
            "UNREGISTERED_ACTION",
            "COMPLETE",
            "LOW",
            True,
            False,
        ),
        validate_route(
            "production boundary escalates",
            "ESCALATE",
            "RUN_TEST",
            "COMPLETE",
            "LOW",
            True,
            True,
        ),
        validate_route(
            "human-only action escalates",
            "ESCALATE",
            "PRODUCTION_RELEASE",
            "COMPLETE",
            "LOW",
            True,
            False,
        ),
        validate_route(
            "missing evidence holds",
            "HOLD",
            "RUN_TEST",
            "MISSING",
            "LOW",
            True,
            False,
        ),
        validate_route(
            "high risk escalates",
            "ESCALATE",
            "RUN_TEST",
            "COMPLETE",
            "HIGH",
            True,
            False,
        ),
    ]

    learning = learn(True, "tighten validation threshold")
    records.append(
        ValidationRecord(
            scenario="learning cannot auto-apply policy",
            expected="PROPOSE_ONLY",
            actual=learning["policy_effect"],
            passed=learning["policy_effect"] == "PROPOSE_ONLY",
            evidence={"decision": learning["decision"], "proposal": learning["proposal"]},
        )
    )

    return records


def main() -> int:
    records = run()
    payload = {
        "status": "PASS" if all(r.passed for r in records) else "FAIL",
        "production_deployment": "HOLD",
        "records": [asdict(r) for r in records],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
