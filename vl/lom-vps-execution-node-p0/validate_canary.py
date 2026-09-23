from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any

ALLOWED_RESULT = {"PASS", "FAIL", "NOT_RUN"}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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

    evidence_class = str(evidence.get("evidence_class") or "UNCLASSIFIED")
    attestation = evidence.get("node_attestation")
    attestation_valid = False
    node_id = ""
    if evidence_class == "LIVE_VPS_CANARY":
        if isinstance(attestation, dict):
            node_id = str(attestation.get("node_id") or "").strip()
            attestation_valid = all([
                bool(node_id),
                attestation.get("environment_class") == "NON_PRODUCTION_VPS",
                attestation.get("operator_confirmed") is True,
                isinstance(attestation.get("uid"), int) and attestation.get("uid") > 0,
                str(attestation.get("hostname_hash") or "").startswith("sha256:"),
                str(attestation.get("boot_id_hash") or "").startswith("sha256:"),
                str(attestation.get("collector_version") or "") == "1.0",
                bool(SHA_RE.fullmatch(str(attestation.get("repo_sha") or ""))),
                isinstance(attestation.get("observed_at_epoch"), int) and attestation.get("observed_at_epoch") > 0,
            ])
        if not attestation_valid:
            violations.append("LIVE_NODE_ATTESTATION_INVALID")

    source_prefix = f"vps:{node_id}:" if node_id else ""
    live_sources = bool(by_name) and bool(source_prefix) and all(
        str(row.get("source_reference") or "").startswith(source_prefix)
        for row in by_name.values()
    )
    live_candidate = evidence_class == "LIVE_VPS_CANARY" and attestation_valid and live_sources
    live_vps_verified = status == "PASS" and live_candidate and not violations
    if evidence_class == "LIVE_VPS_CANARY" and not live_sources:
        violations.append("LIVE_SOURCE_BINDING_INVALID")
        live_vps_verified = False
    if violations and status == "PASS":
        status = "HOLD"
        reason = "CANARY_NOT_PROVEN"

    observed_times = [
        row.get("observed_at_epoch")
        for row in by_name.values()
        if isinstance(row.get("observed_at_epoch"), int) and row.get("observed_at_epoch") > 0
    ]

    body = {
        "schema": "lom.vps-canary-resolution/1",
        "status": status,
        "reason": reason,
        "missing_checks": missing,
        "unknown_checks": unknown,
        "failed_checks": failed,
        "not_run_checks": not_run,
        "violations": sorted(violations),
        "evidence_class": evidence_class,
        "node_id": node_id or None,
        "attestation_valid": attestation_valid,
        "observed_at_epoch": min(observed_times) if observed_times else None,
        "live_sources": live_sources,
        "live_vps_verified": live_vps_verified,
        "activation_status": "READY" if live_vps_verified else "HOLD",
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "connector_execution": "DISABLED",
    }
    return {**body, "resolution_digest": _digest(body)}
