#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ObservabilityError(ValueError):
    pass


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_time(value: str) -> datetime:
    if not value:
        raise ObservabilityError("started_at required")
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify(run: dict[str, Any], *, now: datetime, stale_after_seconds: int) -> dict[str, Any]:
    if stale_after_seconds <= 0:
        raise ObservabilityError("stale_after_seconds must be positive")
    required = ["id", "state", "started_at", "runner_status", "runner_qa_result", "deployment_count", "workflow_state"]
    missing = [k for k in required if run.get(k) in (None, "")]
    if missing:
        return decision(run, "REVIEW_REQUIRED", "MISSING_OBSERVABILITY_FIELDS", {"missing": missing})

    age_seconds = max(0, int((now - parse_time(str(run["started_at"]))).total_seconds()))
    stale = age_seconds >= stale_after_seconds
    validating = run.get("state") == "validating"
    runner_pass = run.get("runner_status") == "PASS" and run.get("runner_qa_result") == "PASS"
    no_deployment = int(run.get("deployment_count") or 0) == 0
    workflow_running = run.get("workflow_state") == "running"
    current_path = bool(run.get("default_environments_present"))

    evidence = {
        "age_seconds": age_seconds,
        "stale_after_seconds": stale_after_seconds,
        "stale": stale,
        "validating": validating,
        "runner_pass": runner_pass,
        "no_deployment": no_deployment,
        "workflow_running": workflow_running,
        "default_environments_present": current_path,
    }

    if validating and runner_pass and no_deployment and workflow_running and stale:
        if current_path:
            return decision(run, "CURRENT_PATH_REGRESSION_REQUIRES_REVIEW", "STALE_VALIDATING_RUN_ON_CURRENT_PROVISIONING_PATH", evidence)
        return decision(run, "HISTORICAL_ORPHAN_CANDIDATE", "STALE_VALIDATING_RUN_WITH_RUNNER_PASS_NO_DEPLOYMENT", evidence)

    return decision(run, "NO_ACTION", "NO_ORPHAN_PATTERN", evidence)


def decision(run: dict[str, Any], classification: str, reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    safe_identity = {
        "factory_run_id": run.get("id"),
        "project_id": run.get("project_id"),
        "state": run.get("state"),
        "workflow_state": run.get("workflow_state"),
        "runner_status": run.get("runner_status"),
        "runner_qa_result": run.get("runner_qa_result"),
        "deployment_count": run.get("deployment_count"),
    }
    out = {
        "schema": "vl.factory-run-observability/1",
        "classification": classification,
        "reason_code": reason,
        "factory_run_id": run.get("id"),
        "project_id": run.get("project_id"),
        "evidence": evidence,
        "source_digest_sha256": canonical_sha(safe_identity),
        "mutation_performed": False,
        "production_authority": False,
    }
    out["decision_sha256"] = canonical_sha(out)
    return out


def blocked_event(*, factory_run_id: str, reason_code: str, source_decision: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema": "vl.observability-event/1",
        "event_type": "release_candidate_blocked_observed",
        "factory_run_id": factory_run_id,
        "reason_code": reason_code,
        "source_decision_sha256": source_decision.get("decision_sha256"),
        "mutation_performed": False,
        "production_authority": False,
        "secret_values_recorded": False,
    }
    payload["event_sha256"] = canonical_sha(payload)
    return payload


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: classify_stale_factory_run.py <run.json> <now-iso> <stale-after-seconds>", file=sys.stderr)
        return 2
    try:
        run = json.loads(Path(sys.argv[1]).read_text())
        result = classify(run, now=parse_time(sys.argv[2]), stale_after_seconds=int(sys.argv[3]))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"ORPHAN OBSERVABILITY: FAIL - {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
