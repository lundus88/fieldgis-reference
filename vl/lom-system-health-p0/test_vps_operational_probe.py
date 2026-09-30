from vps_operational_probe import REQUIRED_UNITS, assess_snapshot


def healthy_snapshot():
    return {
        "services": {
            unit: {"enabled": "enabled", "active": "active"}
            for unit in REQUIRED_UNITS
        },
        "ingress": {
            "status": "READY",
            "production": False,
            "production_locked": True,
            "queue_depth": 0,
        },
        "ingress_error": None,
        "canary": {
            "status": "PASS",
            "activation_status": "READY",
            "live_vps_verified": True,
            "failed_checks": [],
            "missing_checks": [],
            "violations": [],
            "runtime_host_policy": "VPS_ONLY",
            "node_id": "v103067",
            "production_authority": "HUMAN_ONLY",
        },
        "canary_error": None,
        "disk_free_pct": 74.5,
    }


def test_healthy_snapshot_passes():
    result = assess_snapshot(healthy_snapshot())
    assert result["status"] == "HEALTHY"
    assert result["reasons"] == []
    assert result["runtime_host_policy"] == "VPS_ONLY"
    assert result["production_authority"] == "HUMAN_ONLY"


def test_ingress_public_or_unlocked_fails_closed():
    snap = healthy_snapshot()
    snap["ingress"]["production_locked"] = False
    snap["ingress"]["production"] = True
    result = assess_snapshot(snap)
    assert result["status"] == "HOLD"
    assert "INGRESS_PRODUCTION_NOT_LOCKED" in result["reasons"]
    assert "INGRESS_PRODUCTION_FLAG_INVALID" in result["reasons"]


def test_service_regression_fails_closed():
    snap = healthy_snapshot()
    snap["services"]["lom-worker.service"]["active"] = "inactive"
    result = assess_snapshot(snap)
    assert result["status"] == "HOLD"
    assert "lom-worker.service:NOT_ACTIVE" in result["reasons"]


def test_canary_regression_fails_closed():
    snap = healthy_snapshot()
    snap["canary"]["status"] = "HOLD"
    snap["canary"]["violations"] = ["example"]
    result = assess_snapshot(snap)
    assert result["status"] == "HOLD"
    assert "LIVE_CANARY_NOT_PASS" in result["reasons"]
    assert "LIVE_CANARY_VIOLATIONS" in result["reasons"]


def test_low_disk_fails_closed():
    snap = healthy_snapshot()
    snap["disk_free_pct"] = 9.0
    result = assess_snapshot(snap)
    assert result["status"] == "HOLD"
    assert "DISK_FREE_BELOW_15_PERCENT" in result["reasons"]


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} VPS operational hardening tests")
