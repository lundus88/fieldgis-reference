from __future__ import annotations

from typing import Any

ALLOWED_ORGANS = {"eyes"}
STATUS_MAP = {
    "HEALTHY": "HEALTHY",
    "DEGRADED": "DEGRADED",
    "HOLD": "HOLD",
    "ACTION_REQUIRED": "HOLD",
}


def portfolio_snapshot_to_organ_probe(
    snapshot: dict[str, Any],
    *,
    now_epoch: int,
    organ: str = "eyes",
) -> dict[str, Any]:
    """Translate verified System Health output into a BodyRuntime organ probe.

    This adapter does not execute recovery. It only converts already-derived
    portfolio health evidence into the homeostasis contract used by LOM.
    """

    if organ not in ALLOWED_ORGANS:
        return {
            "organ": organ,
            "status": "HOLD",
            "observed_at_epoch": now_epoch,
            "evidence_refs": ["health-adapter:invalid-organ"],
            "reason": "HEALTH_ADAPTER_ORGAN_FORBIDDEN",
        }

    if snapshot.get("schema") != "lom.portfolio-health/1":
        return _hold(organ, now_epoch, "PORTFOLIO_HEALTH_SCHEMA_INVALID")

    portfolio_digest = str(snapshot.get("portfolio_digest") or "")
    if not portfolio_digest:
        return _hold(organ, now_epoch, "PORTFOLIO_HEALTH_DIGEST_REQUIRED")

    observed = snapshot.get("observed_at_epoch")
    fresh_until = snapshot.get("fresh_until_epoch")
    if not isinstance(observed, int) or observed <= 0:
        return _hold(organ, now_epoch, "PORTFOLIO_HEALTH_TIME_REQUIRED")
    if not isinstance(fresh_until, int) or fresh_until < observed:
        return _hold(organ, observed, "PORTFOLIO_FRESHNESS_INVALID")
    if observed > now_epoch:
        return _hold(organ, observed, "PORTFOLIO_HEALTH_FROM_FUTURE")
    if fresh_until < now_epoch:
        return _hold(organ, observed, "PORTFOLIO_HEALTH_STALE")

    source_status = snapshot.get("overall")
    mapped = STATUS_MAP.get(source_status)
    if mapped is None:
        return _hold(organ, observed, "PORTFOLIO_HEALTH_STATUS_UNKNOWN")

    reasons = [
        reason
        for project in snapshot.get("projects") or []
        for reason in project.get("reasons") or []
        if reason != "PROJECT_EVIDENCE_COMPLETE"
    ]

    return {
        "organ": organ,
        "status": mapped,
        "observed_at_epoch": observed,
        "evidence_refs": [f"portfolio-health:{portfolio_digest}"],
        "reason": (
            "PORTFOLIO_ACTION_REQUIRED"
            if source_status == "ACTION_REQUIRED"
            else (reasons[0] if reasons else "PORTFOLIO_HEALTH_CURRENT")
        ),
        "source_status": source_status,
        "fresh_until_epoch": fresh_until,
        "execution_authority": "NONE",
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
    }


def _hold(organ: str, observed_at_epoch: int, reason: str) -> dict[str, Any]:
    return {
        "organ": organ,
        "status": "HOLD",
        "observed_at_epoch": observed_at_epoch,
        "evidence_refs": [f"health-adapter:{reason.lower()}"],
        "reason": reason,
        "execution_authority": "NONE",
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
    }
