from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


VALID_CLASSIFICATIONS = {"public", "internal", "confidential", "restricted"}
VALID_RETENTION = {"standard", "short", "regulated"}


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class EffectivePolicy:
    capabilities: frozenset[str]
    classifications: frozenset[str]
    retention_profiles: frozenset[str]
    restricted_projects: frozenset[str]


def _as_set(values: Iterable[str] | None) -> frozenset[str]:
    return frozenset(values or ())


def derive_effective_policy(parent: Mapping, child: Mapping) -> EffectivePolicy:
    """Return child policy narrowed by parent. Any attempted widening fails closed."""
    p_caps = _as_set(parent.get("capabilities"))
    c_caps = _as_set(child.get("capabilities"))
    p_cls = _as_set(parent.get("classifications"))
    c_cls = _as_set(child.get("classifications"))
    p_ret = _as_set(parent.get("retention_profiles"))
    c_ret = _as_set(child.get("retention_profiles"))
    p_restricted = _as_set(parent.get("restricted_projects"))
    c_restricted = _as_set(child.get("restricted_projects"))

    if not c_caps.issubset(p_caps):
        raise PolicyError("child capability widens parent authority")
    if not c_cls.issubset(p_cls):
        raise PolicyError("child classification widens parent authority")
    if not c_ret.issubset(p_ret):
        raise PolicyError("child retention profile widens parent authority")
    if not c_restricted.issubset(p_restricted):
        raise PolicyError("child restricted-project scope widens parent authority")

    unknown_cls = c_cls - VALID_CLASSIFICATIONS
    unknown_ret = c_ret - VALID_RETENTION
    if unknown_cls:
        raise PolicyError(f"unknown classification: {sorted(unknown_cls)}")
    if unknown_ret:
        raise PolicyError(f"unknown retention profile: {sorted(unknown_ret)}")

    return EffectivePolicy(c_caps, c_cls, c_ret, c_restricted)


def authorize_data_access(
    effective: EffectivePolicy,
    *,
    project_id: str,
    classification: str,
    retention_profile: str,
    capability: str,
) -> dict:
    """Fail closed for unknown data classes/retention or any missing inherited scope."""
    if classification not in VALID_CLASSIFICATIONS:
        return {"decision": "deny", "reason": "UNKNOWN_CLASSIFICATION"}
    if retention_profile not in VALID_RETENTION:
        return {"decision": "deny", "reason": "UNKNOWN_RETENTION_PROFILE"}
    if capability not in effective.capabilities:
        return {"decision": "deny", "reason": "CAPABILITY_NOT_EFFECTIVE"}
    if classification not in effective.classifications:
        return {"decision": "deny", "reason": "CLASSIFICATION_NOT_EFFECTIVE"}
    if retention_profile not in effective.retention_profiles:
        return {"decision": "deny", "reason": "RETENTION_NOT_EFFECTIVE"}
    if classification == "restricted" and project_id not in effective.restricted_projects:
        return {"decision": "deny", "reason": "RESTRICTED_PROJECT_GRANT_REQUIRED"}
    return {
        "decision": "allow",
        "reason": "EFFECTIVE_POLICY_MATCH",
        "project_id": project_id,
        "classification": classification,
        "retention_profile": retention_profile,
        "capability": capability,
    }
