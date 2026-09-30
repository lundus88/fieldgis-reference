from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any
from urllib.request import urlopen


REQUIRED_UNITS = (
    "lom-worker.service",
    "lom-heartbeat.timer",
    "lom-secure-ingress.service",
)
DEFAULT_CANARY = Path("/home/lom-runner/lom-vps-canary-resolution.json")
DEFAULT_HEALTH_URL = "http://127.0.0.1:8765/health"


def _systemctl(action: str, unit: str) -> str:
    result = subprocess.run(
        ["systemctl", action, unit],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return (result.stdout or result.stderr).strip()


def _load_health(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=2) as response:
        if response.status != 200:
            raise RuntimeError(f"INGRESS_HEALTH_HTTP_{response.status}")
        return json.loads(response.read().decode("utf-8"))


def _load_canary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_snapshot(
    *,
    canary_path: Path = DEFAULT_CANARY,
    health_url: str = DEFAULT_HEALTH_URL,
    disk_path: str = "/",
) -> dict[str, Any]:
    services = {
        unit: {
            "enabled": _systemctl("is-enabled", unit),
            "active": _systemctl("is-active", unit),
        }
        for unit in REQUIRED_UNITS
    }

    health_error = None
    try:
        ingress = _load_health(health_url)
    except Exception as exc:
        ingress = {}
        health_error = f"{type(exc).__name__}:{exc}"

    canary_error = None
    try:
        canary = _load_canary(canary_path)
    except Exception as exc:
        canary = {}
        canary_error = f"{type(exc).__name__}:{exc}"

    usage = shutil.disk_usage(disk_path)
    disk_free_pct = round((usage.free / usage.total) * 100, 2) if usage.total else 0.0

    return {
        "services": services,
        "ingress": ingress,
        "ingress_error": health_error,
        "canary": canary,
        "canary_error": canary_error,
        "disk_free_pct": disk_free_pct,
    }


def assess_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []

    services = snapshot.get("services", {})
    for unit in REQUIRED_UNITS:
        state = services.get(unit, {})
        if state.get("enabled") != "enabled":
            reasons.append(f"{unit}:NOT_ENABLED")
        if state.get("active") != "active":
            reasons.append(f"{unit}:NOT_ACTIVE")

    ingress = snapshot.get("ingress") or {}
    if snapshot.get("ingress_error"):
        reasons.append("INGRESS_HEALTH_UNAVAILABLE")
    if ingress.get("status") != "READY":
        reasons.append("INGRESS_NOT_READY")
    if ingress.get("production") is not False:
        reasons.append("INGRESS_PRODUCTION_FLAG_INVALID")
    if ingress.get("production_locked") is not True:
        reasons.append("INGRESS_PRODUCTION_NOT_LOCKED")

    canary = snapshot.get("canary") or {}
    if snapshot.get("canary_error"):
        reasons.append("LIVE_CANARY_UNAVAILABLE")
    if canary.get("status") != "PASS":
        reasons.append("LIVE_CANARY_NOT_PASS")
    if canary.get("activation_status") != "READY":
        reasons.append("LIVE_CANARY_NOT_READY")
    if canary.get("live_vps_verified") is not True:
        reasons.append("LIVE_VPS_NOT_VERIFIED")
    if canary.get("failed_checks"):
        reasons.append("LIVE_CANARY_FAILED_CHECKS")
    if canary.get("missing_checks"):
        reasons.append("LIVE_CANARY_MISSING_CHECKS")
    if canary.get("violations"):
        reasons.append("LIVE_CANARY_VIOLATIONS")

    try:
        disk_free_pct = float(snapshot.get("disk_free_pct", 0))
    except (TypeError, ValueError):
        disk_free_pct = 0
    if disk_free_pct < 15:
        reasons.append("DISK_FREE_BELOW_15_PERCENT")

    return {
        "status": "HEALTHY" if not reasons else "HOLD",
        "reasons": sorted(set(reasons)),
        "runtime_host_policy": canary.get("runtime_host_policy"),
        "node_id": canary.get("node_id"),
        "production_authority": canary.get("production_authority"),
        "services": services,
        "ingress": ingress,
        "disk_free_pct": disk_free_pct,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only LOM VPS operational readiness probe")
    parser.add_argument("--canary", type=Path, default=DEFAULT_CANARY)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--disk-path", default="/")
    args = parser.parse_args()

    assessment = assess_snapshot(
        collect_snapshot(
            canary_path=args.canary,
            health_url=args.health_url,
            disk_path=args.disk_path,
        )
    )
    print(json.dumps(assessment, sort_keys=True))
    return 0 if assessment["status"] == "HEALTHY" else 2


if __name__ == "__main__":
    sys.exit(main())
