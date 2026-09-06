from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Dict, Iterable, Mapping, Optional

ALLOWED_PROTOCOLS = {"oidc", "saml"}
ALLOWED_SCIM_OPERATIONS = {"USER_CREATE", "USER_UPDATE", "USER_DISABLE", "GROUP_MEMBERSHIP_SYNC"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class FederatedIdentity:
    protocol: str
    issuer: str
    subject: str
    workspace_id: str
    email: Optional[str]
    groups: tuple[str, ...]
    authenticated_at: str

    def normalized(self) -> Dict[str, Any]:
        if self.protocol not in ALLOWED_PROTOCOLS:
            raise ValueError("UNSUPPORTED_FEDERATION_PROTOCOL")
        if not self.issuer or not self.subject or not self.workspace_id:
            raise ValueError("INCOMPLETE_FEDERATED_IDENTITY")
        payload = asdict(self)
        payload["groups"] = sorted(set(self.groups))
        payload["identity_fingerprint"] = _digest({
            "protocol": self.protocol,
            "issuer": self.issuer,
            "subject": self.subject,
            "workspace_id": self.workspace_id,
        })
        return payload


def normalize_identity_assertion(assertion: Mapping[str, Any]) -> Dict[str, Any]:
    identity = FederatedIdentity(
        protocol=str(assertion.get("protocol", "")).lower(),
        issuer=str(assertion.get("issuer", "")),
        subject=str(assertion.get("subject", "")),
        workspace_id=str(assertion.get("workspace_id", "")),
        email=assertion.get("email"),
        groups=tuple(str(x) for x in assertion.get("groups", [])),
        authenticated_at=str(assertion.get("authenticated_at", "")),
    )
    return identity.normalized()


def plan_scim_change(
    *,
    operation: str,
    workspace_id: str,
    external_subject: str,
    target_roles: Iterable[str],
    allowed_roles: Iterable[str],
    dry_run: bool = True,
) -> Dict[str, Any]:
    if operation not in ALLOWED_SCIM_OPERATIONS:
        raise ValueError("SCIM_OPERATION_DENIED")
    if not workspace_id or not external_subject:
        raise ValueError("SCIM_SCOPE_REQUIRED")
    if not dry_run:
        raise ValueError("SCIM_LIVE_PROVISIONING_NOT_ENABLED")

    requested_roles = sorted(set(target_roles))
    allowed = set(allowed_roles)
    unauthorized = [role for role in requested_roles if role not in allowed]
    if unauthorized:
        raise ValueError("SCIM_ROLE_SCOPE_DENIED")

    plan = {
        "schema": "vl.scim-provisioning-plan/1",
        "mode": "DRY_RUN_ONLY",
        "operation": operation,
        "workspace_id": workspace_id,
        "external_subject_fingerprint": _digest({
            "workspace_id": workspace_id,
            "external_subject": external_subject,
        }),
        "target_roles": requested_roles,
        "production_authority": False,
        "live_provisioning": False,
    }
    plan["plan_sha256"] = _digest(plan)
    return plan
