from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

ALLOWED_RESULT = {"PASS", "FAIL", "NOT_RUN"}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def validate_canary(contract: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    if contract.get("version") != "1.0" or contract.get("mode") != "NON_PRODUCTION_CANARY":
        return {"status": "HOLD", "reason": "CANARY_CONTRACT_INVALID"}
    required = contract.get("required_checks")
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
        return {"status": "HOLD", "reason": "CANARY_CHECK_SET_INVALID"}

    authority = contract.get("authority") or {}
    if authority.get("autonomous_ceiling") != "PREPARE_PR":
        return {"status": "HOLD", "reason": "AUTONOMOUS_CEILING_WEAKENED"}
    if authority.get("protected_main_merge") != "HUMAN_ONLY":
        return {"status": "HOLD", "reason": "MERGE_AUTHORITY_WEAKENED"}
    if authority.get("production_deploy") != "HUMAN_ONLY":
        return {"status": "HOLD", "reason": "PRODUCTION_AUTHORITY_WEAKENED"}
    if authority.get("connector_execution_during_p0_canary") != "DISABLED":
        return {"status": "HOLD", "reason": "CONNECTOR_CANARY_BOUNDARY_WEAKENED"}

    rows = evidence.get("checks")
    if evidence.get("schema") != "lom.vps-canary-evidence/1" or not isinstance(rows, list):
        return {"status": "HOLD", "reason": "CANARY_EVIDENCE_SCHEMA_INVALID"}

    by_name: dict[str, dict[str, Any]] = {}
    violations: list[str] = []
    for row in rows:
        name = row.get("name")
        result = row.get("result")
        source = str(row.get("source_reference") or "").strip()
        observed = row.get("observed_at_epoch")
        if not name or name in by_name:
            violations.append("DUPLICATE_OR_MISSING_CHECK")
            continue
        if result not in ALLOWED_RESULT:
            violations.append(f"INVALID_RESULT:{name}")
            continue
        if not source or not isinstance(observed, int) or observed <= 0:
            violations.append(f"EVIDENCE_INCOMPLETE:{name}")
            continue
        by_name[name] = row

    missing = sorted(set(required) - set(by_name))
    unknown = sorted(set(by_name) - set(required))
    failed = sorted(name for name in required if by_name.get(name, {}).get("result") == "FAIL")
    not_run = sorted(name for name in required if by_name.get(name, {}).get("result") == "NOT_RUN")

    status = "PASS"
    reason = "ALL_REQUIRED_CHECKS_PASS"
    if violations or missing or unknown or failed or not_run:
        status = "HOLD"
        reason = "CANARY_NOT_PROVEN"

    body = {
        "schema": "lom.vps-canary-resolution/1",
        "status": status,
        "reason": reason,
        "missing_checks": missing,
        "unknown_checks": unknown,
        "failed_checks": failed,
        "not_run_checks": not_run,
        "violations": sorted(violations),
        "live_vps_verified": status == "PASS",
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "connector_execution": "DISABLED",
    }
    return {**body, "resolution_digest": _digest(body)}
