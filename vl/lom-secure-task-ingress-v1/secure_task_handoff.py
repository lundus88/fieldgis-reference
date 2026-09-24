from __future__ import annotations

from typing import Any, Callable

from secure_task_ingress import SecureTaskIngress, digest


class SecureTaskHandoff:
    """Bridge durable ingress leases to authoritative ACP-backed execution.

    grant_loader MUST resolve grant_ref from the authoritative ACP store. The
    inbound envelope never carries an executable grant.
    """

    def __init__(
        self,
        *,
        ingress: SecureTaskIngress,
        grant_loader: Callable[[str], dict[str, Any] | None],
        executor_factory: Callable[[dict[str, Any], str], Callable[[dict[str, Any]], dict[str, Any]]],
    ) -> None:
        self.ingress = ingress
        self.grant_loader = grant_loader
        self.executor_factory = executor_factory

    def run_once(
        self,
        *,
        owner_id: str,
        lease_seconds: int = 60,
        now=None,
    ) -> dict[str, Any]:
        claim = self.ingress.claim_next(
            owner_id=owner_id,
            lease_seconds=lease_seconds,
            now=now,
        )
        if claim.get("decision") != "CLAIMED":
            return claim

        envelope = claim["envelope"]
        task_id = claim["task_id"]
        lease_token = claim["lease_token"]
        grant_ref = envelope["grant_ref"]
        grant = self.grant_loader(grant_ref)

        if not isinstance(grant, dict):
            nack = self.ingress.nack(
                task_id=task_id,
                lease_token=lease_token,
                reason="AUTHORITATIVE_GRANT_UNAVAILABLE",
                permanent=True,
                now=now,
            )
            return {
                "decision": "HOLD",
                "reason": "AUTHORITATIVE_GRANT_UNAVAILABLE",
                "task_id": task_id,
                "queue_result": nack,
                "production": False,
                "production_locked": True,
            }

        # Minimum pre-execution binding. The ACP + executor remain authoritative
        # and perform the full capability/scope/policy decision.
        scope = grant.get("scope") or {}
        if (
            scope.get("project_id") != envelope["body_request"].get("project_id")
            or scope.get("target_environment") != envelope["target_environment"]
        ):
            nack = self.ingress.nack(
                task_id=task_id,
                lease_token=lease_token,
                reason="AUTHORITATIVE_GRANT_SCOPE_MISMATCH",
                permanent=True,
                now=now,
            )
            return {
                "decision": "HOLD",
                "reason": "AUTHORITATIVE_GRANT_SCOPE_MISMATCH",
                "task_id": task_id,
                "queue_result": nack,
                "production": False,
                "production_locked": True,
            }

        try:
            executor = self.executor_factory(grant, envelope["target_environment"])
            execution = executor(envelope["body_request"])
        except Exception as exc:
            nack = self.ingress.nack(
                task_id=task_id,
                lease_token=lease_token,
                reason="EXECUTOR_EXCEPTION",
                permanent=False,
                now=now,
            )
            return {
                "decision": "HOLD",
                "reason": "EXECUTOR_EXCEPTION",
                "error_type": type(exc).__name__,
                "task_id": task_id,
                "queue_result": nack,
                "production": False,
                "production_locked": True,
            }

        if execution.get("decision") == "ALLOW":
            result_digest = digest(execution)
            ack = self.ingress.ack(
                task_id=task_id,
                lease_token=lease_token,
                result_digest=result_digest,
                now=now,
            )
            return {
                "decision": "ALLOW",
                "reason": "AUTHORITATIVE_ACP_EXECUTION_ACKED",
                "task_id": task_id,
                "result_digest": result_digest,
                "execution": execution,
                "queue_result": ack,
                "production": False,
                "production_locked": True,
            }

        reason = str(execution.get("reason") or "ACP_OR_EXECUTOR_DENIED")
        safe_reason = reason if reason and all(ch.isupper() or ch.isdigit() or ch in "._:-" for ch in reason) else "ACP_OR_EXECUTOR_DENIED"
        nack = self.ingress.nack(
            task_id=task_id,
            lease_token=lease_token,
            reason=safe_reason[:160],
            permanent=True,
            now=now,
        )
        return {
            "decision": "HOLD",
            "reason": reason,
            "task_id": task_id,
            "execution": execution,
            "queue_result": nack,
            "production": False,
            "production_locked": True,
        }
