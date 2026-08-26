#!/usr/bin/env python3
"""Fail-closed helpers shared by the VL production promoter and regression tests."""
from __future__ import annotations

import hashlib
from pathlib import Path


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
