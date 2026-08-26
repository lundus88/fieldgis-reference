#!/usr/bin/env python3
"""Fail-closed helpers shared by the VL production promoter and regression tests."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ADAPTERS = {
    "mobile-flutter-v1": {
        "key": "mobile-release-artifact", "target": "android_distribution_artifact",
        "required": (), "deploy": True, "rollback": True, "health": True,
    },
    "web-react-v1": {
        "key": "vercel-production", "target": "vercel_production",
        "required": ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"),
        "deploy": True, "rollback": True, "health": True,
    },
    "pwa-react-v1": {
        "key": "vercel-pwa-production", "target": "vercel_production",
        "required": ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"),
        "deploy": True, "rollback": True, "health": True,
    },
    "gis-web-v1": {
        "key": "vercel-gis-production", "target": "vercel_production",
        "required": ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"),
        "deploy": True, "rollback": True, "health": True,
    },
    "api-service-v1": {
        "key": "supabase-edge-function", "target": "supabase_edge_function",
        "required": ("SUPABASE_ACCESS_TOKEN", "SUPABASE_PROJECT_REF", "SUPABASE_FUNCTION_NAME"),
        "deploy": True, "rollback": True, "health": True,
    },
}


def adapter_for(builder_key: str) -> dict:
    try:
        return ADAPTERS[builder_key]
    except KeyError as exc:
        raise ValueError(f"UNCONFIGURED: no production adapter for {builder_key}") from exc


def configuration_status(builder_key: str, environment: dict[str, str]) -> tuple[str, list[str]]:
    adapter = adapter_for(builder_key)
    missing = [name for name in adapter["required"] if not environment.get(name)]
    return ("BLOCKED/UNCONFIGURED", missing) if missing else ("CONFIGURED", [])


def verify_sha256(path: str | Path, expected: str) -> str:
    expected = expected.strip().lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("invalid certified SHA256")
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError(f"artifact SHA256 mismatch: expected {expected}, got {digest}")
    return digest


def callback_is_current(job: dict, lease_token: str) -> bool:
    return job.get("state") == "leased" and bool(lease_token) and job.get("lease_token") == lease_token


def evidence(check_key: str, expected, actual, passed: bool) -> dict:
    return {
        "check_key": check_key, "expected": expected, "actual": actual,
        "status": "PASS" if passed else "FAIL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def verify_http_contract(
    url: str,
    *,
    expected_status: int = 200,
    expected_json: dict | None = None,
    required_text: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15,
    opener=urlopen,
) -> list[dict]:
    """Return evidence for reachability and response contracts; never throws a false PASS."""
    checks: list[dict] = []
    try:
        response = opener(Request(url, headers=headers or {}), timeout=timeout)
        status = int(response.status)
        body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        status, body = exc.code, exc.read().decode("utf-8", errors="replace")
    except (URLError, OSError, TimeoutError) as exc:
        return [evidence("reachable", True, f"{type(exc).__name__}: {exc}", False)]
    checks.append(evidence("http_status", expected_status, status, status == expected_status))
    if required_text is not None:
        checks.append(evidence("app_boot", required_text, required_text if required_text in body else "missing", required_text in body))
    if expected_json is not None:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = None
        for key, expected in expected_json.items():
            actual = payload.get(key) if isinstance(payload, dict) else None
            checks.append(evidence(f"response.{key}", expected, actual, actual == expected))
    return checks


def all_checks_pass(checks: list[dict]) -> bool:
    return bool(checks) and all(item.get("status") == "PASS" for item in checks)


def require_previous_certified(deployments: list[dict], current_id: str) -> dict:
    candidates = [
        item for item in deployments
        if item.get("id") != current_id
        and item.get("status") in {"deployed", "rolled_back"}
        and item.get("certificate", {}).get("technical_validation") == "PASS"
        and item.get("artifact_sha256")
        and item.get("provider_deployment_id")
    ]
    if not candidates:
        raise ValueError("rollback blocked: previous certified provider deployment required")
    return max(candidates, key=lambda item: item.get("deployed_at") or "")
