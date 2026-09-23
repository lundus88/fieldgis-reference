from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Callable

from runner import ExecutionJournal, NodeTask, execute_node_action
from validate_canary import validate_canary

SAFE_BODY_ACTIONS = {
    "PREPARE_PREVIEW_REFRESH",
    "PREPARE_EXACT_MAIN_CI_REFRESH",
    "PREPARE_CI_REMEDIATION_PR",
    "PREPARE_RUNTIME_DIAGNOSTIC_PR",
    "PREPARE_REGRESSION_EVIDENCE_REFRESH",
    "PREPARE_JOURNEY_BINDING_PR",
    "PREPARE_NONCRITICAL_REMEDIATION_PR",
    "NON_PROD_CODE",
}


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


class VPSBodyExecutorAdapter:
    """Bind BodyRuntime bounded delegation to the least-privilege VPS runner.

    Activation requires fresh, non-synthetic live VPS canary evidence on every
    invocation. This adapter never widens capability, target environment or
    Production authority.
    """

    def __init__(
        self,
        *,
        grant: dict[str, Any],
        journal: ExecutionJournal,
        canary_contract: dict[str, Any],
        canary_evidence: dict[str, Any],
        target_environment: str = "staging",
        max_canary_age_seconds: int = 900,
        environment: dict[str, str] | None = None,
        replay_record: dict[str, str] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.grant = grant
        self.journal = journal
        self.canary_contract = canary_contract
        self.canary_evidence = canary_evidence
        self.target_environment = target_environment
        self.max_canary_age_seconds = max_canary_age_seconds
        self.environment = {} if environment is None else environment
        self.replay_record = {} if replay_record is None else replay_record
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _activation_gate(self, *, now_epoch: int) -> dict[str, Any]:
        if self.target_environment not in {"development", "staging"}:
            return {"status": "HOLD", "reason": "NON_PRODUCTION_SCOPE_REQUIRED"}
        if self.max_canary_age_seconds <= 0:
            return {"status": "HOLD", "reason": "CANARY_MAX_AGE_INVALID"}

        resolution = validate_canary(self.canary_contract, self.canary_evidence)
        if resolution.get("status") != "PASS":
            return {"status": "HOLD", "reason": "LIVE_VPS_CANARY_NOT_PASS", "resolution": resolution}
        if resolution.get("live_vps_verified") is not True or resolution.get("activation_status") != "READY":
            return {"status": "HOLD", "reason": "LIVE_VPS_NOT_VERIFIED", "resolution": resolution}

        observed = resolution.get("observed_at_epoch")
        if not isinstance(observed, int) or observed <= 0 or observed > now_epoch:
            return {"status": "HOLD", "reason": "LIVE_VPS_CANARY_TIME_INVALID", "resolution": resolution}
        if now_epoch - observed > self.max_canary_age_seconds:
            return {"status": "HOLD", "reason": "LIVE_VPS_CANARY_STALE", "resolution": resolution}

        return {"status": "READY", "reason": "LIVE_VPS_CANARY_CURRENT", "resolution": resolution}

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        now = self.clock().astimezone(timezone.utc)
        now_epoch = int(now.timestamp())
        gate = self._activation_gate(now_epoch=now_epoch)
        if gate["status"] != "READY":
            return {
                "decision": "HOLD",
                "reason": gate["reason"],
                "production": False,
                "production_locked": True,
                "canary": gate.get("resolution"),
            }

        if request.get("schema") != "lom.organism-bounded-delegation/1":
            return self._hold("BODY_DELEGATION_SCHEMA_INVALID")
        if request.get("production") is not False or request.get("production_locked") is not True:
            return self._hold("BODY_PRODUCTION_BOUNDARY_INVALID")
        if request.get("max_authority") != "PREPARE_PR":
            return self._hold("BODY_AUTHORITY_CEILING_INVALID")

        requested_action = str(request.get("requested_action") or "")
        if requested_action not in SAFE_BODY_ACTIONS:
            return self._hold("BODY_ACTION_NOT_REGISTERED")

        project_id = str(request.get("project_id") or "")
        evidence_refs = request.get("evidence_refs")
        route_digest = str(request.get("route_digest") or "")
        idempotency_key = str(request.get("idempotency_key") or "")
        if not project_id or not route_digest or not idempotency_key:
            return self._hold("BODY_DELEGATION_IDENTITY_REQUIRED")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            return self._hold("BODY_DELEGATION_EVIDENCE_REQUIRED")

        grant_scope = self.grant.get("scope") or {}
        if grant_scope.get("project_id") != project_id:
            return self._hold("GRANT_PROJECT_SCOPE_MISMATCH")
        if grant_scope.get("target_environment") != self.target_environment:
            return self._hold("GRANT_ENVIRONMENT_SCOPE_MISMATCH")
        if "factory.plan" not in set(self.grant.get("capabilities") or []):
            return self._hold("FACTORY_PLAN_CAPABILITY_REQUIRED")

        input_digest = _digest(request)
        action_id = "lom-body-" + sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
        expires = now + timedelta(minutes=5)
        budget = self.grant.get("budget") or {}

        action = {
            "schema_version": "1.0",
            "action_id": action_id,
            "requested_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": expires.isoformat().replace("+00:00", "Z"),
            "requester": {
                "agent_id": "lom-vps-runner",
                "agent_version": "p0-body-adapter",
                "role": "executor",
                "principal_type": "agent",
            },
            "capability": "factory.plan",
            "scope": {
                "project_id": project_id,
                "target_environment": self.target_environment,
            },
            "provenance": {
                "source_type": "body_runtime",
                "source_id": route_digest,
            },
            "input_digest": input_digest,
            "budget": {
                "timeout_seconds": min(int(budget.get("timeout_seconds", 60)), 60),
                "max_retries": 0,
                "max_cost_minor": 0,
            },
        }
        task = NodeTask(
            "prepare_factory_plan",
            {
                "project_id": project_id,
                "requested_action": requested_action,
                "route_digest": route_digest,
                "evidence_refs": sorted(set(str(ref) for ref in evidence_refs if str(ref))),
            },
        )

        result = execute_node_action(
            action=action,
            grant=self.grant,
            task=task,
            journal=self.journal,
            observed_at_epoch=now_epoch,
            replay_record=self.replay_record,
            environment=self.environment,
        )

        if result.get("status") == "SUCCEEDED":
            self.replay_record[action_id] = input_digest
            return {
                "decision": "ALLOW",
                "reason": "VPS_BOUNDED_PREPARATION_VERIFIED",
                "production": False,
                "production_locked": True,
                "action_digest": result.get("action_digest"),
                "node_result": result,
                "canary_resolution_digest": gate["resolution"].get("resolution_digest"),
            }

        if result.get("status") == "IDEMPOTENT_NOOP" and result.get("evidence_id"):
            return {
                "decision": "ALLOW",
                "reason": "VPS_IDEMPOTENT_REPLAY",
                "production": False,
                "production_locked": True,
                "evidence_id": result["evidence_id"],
                "node_result": result,
                "canary_resolution_digest": gate["resolution"].get("resolution_digest"),
            }

        return {
            "decision": "HOLD",
            "reason": result.get("reason", "VPS_NODE_DENIED"),
            "production": False,
            "production_locked": True,
            "node_result": result,
            "canary_resolution_digest": gate["resolution"].get("resolution_digest"),
        }

    def _hold(self, reason: str) -> dict[str, Any]:
        return {
            "decision": "HOLD",
            "reason": reason,
            "production": False,
            "production_locked": True,
        }
