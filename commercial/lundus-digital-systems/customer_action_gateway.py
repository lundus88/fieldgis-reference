#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, FrozenSet
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
IAM_PATH = ROOT / "docs/commercial/lds-customer-org-iam/engine.py"
LIFECYCLE_PATH = ROOT / "docs/commercial/lds-integrated-customer-lifecycle-gate/lifecycle_gate.py"

SCHEMA = "lds.customer-action-gateway/1"
ALLOWED_ACTIONS = {"REQUEST_CHANGE", "UAT_ACCEPT"}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


IAM = _load("lds_customer_org_iam_engine", IAM_PATH)
LIFECYCLE = _load("lds_integrated_customer_lifecycle_gate", LIFECYCLE_PATH)


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _authorize_project_action(*, actor_org: str, resource_org: str, role: str) -> dict[str, Any]:
    request = IAM.AccessRequest(
        actor_org=actor_org,
        resource_org=resource_org,
        role=role,
        action="manage_project",
    )
    return IAM.authorize(request)


def request_change(
    *,
    actor_id: str,
    actor_org: str,
    resource_org: str,
    role: str,
    project_id: str,
    base_scope_version: int,
    requested_change: str,
    submitted_at: str,
    idempotency_key: str,
    consumed_keys: FrozenSet[str] = frozenset(),
) -> dict[str, Any]:
    auth = _authorize_project_action(
        actor_org=actor_org,
        resource_org=resource_org,
        role=role,
    )
    if auth.get("decision") != "ALLOW":
        return {"decision": "DENY", "reason": auth.get("reason", "NOT_AUTHORIZED")}

    if not actor_id or not project_id or not requested_change.strip() or not submitted_at:
        return {"decision": "HOLD", "reason": "REQUIRED_REQUEST_DATA_MISSING"}
    if not isinstance(base_scope_version, int) or base_scope_version < 1:
        return {"decision": "HOLD", "reason": "INVALID_BASE_SCOPE_VERSION"}
    if not idempotency_key:
        return {"decision": "HOLD", "reason": "IDEMPOTENCY_KEY_REQUIRED"}
    if idempotency_key in consumed_keys:
        return {
            "decision": "IDEMPOTENT_REPLAY",
            "reason": "ACTION_ALREADY_PROCESSED",
            "source_truth_mutated": False,
        }

    seed = {
        "org_id": resource_org,
        "project_id": project_id,
        "base_scope_version": base_scope_version,
        "requested_change": requested_change.strip(),
        "requested_by": actor_id,
        "submitted_at": submitted_at,
        "idempotency_key": idempotency_key,
    }
    record = {
        "schema": "lds.client-change-request-intake/1",
        "change_request_id": "CR-" + _digest(seed)[:12].upper(),
        "project_id": project_id,
        "org_id": resource_org,
        "base_scope_version": base_scope_version,
        "requested_change": requested_change.strip(),
        "requested_by": actor_id,
        "requested_at": submitted_at,
        "state": "REQUESTED",
        "scope_impact": "PENDING_REVIEW",
        "cost_impact": "PENDING_REVIEW",
        "time_impact": "PENDING_REVIEW",
        "dependency_impact": "PENDING_REVIEW",
        "risk_impact": "PENDING_REVIEW",
        "decision": None,
        "decision_by": None,
        "decision_at": None,
        "idempotency_key": idempotency_key,
    }
    return {
        "decision": "ALLOW",
        "gateway_schema": SCHEMA,
        "handoff": "LD_CHANGE_REQUEST_SCOPE_LEDGER",
        "handoff_state": "READY_FOR_LEDGER_INTAKE",
        "record": record,
        "record_digest": _digest(record),
        "source_truth_mutated": False,
        "production_authority": "NONE",
        "commercial_approval_authority": "NONE",
    }


def accept_uat(
    *,
    actor_id: str,
    actor_org: str,
    resource_org: str,
    role: str,
    project_id: str,
    current_state: str,
    acceptance_evidence_ref: str,
    accepted_at: str,
    idempotency_key: str,
    consumed_keys: FrozenSet[str] = frozenset(),
) -> dict[str, Any]:
    auth = _authorize_project_action(
        actor_org=actor_org,
        resource_org=resource_org,
        role=role,
    )
    if auth.get("decision") != "ALLOW":
        return {"decision": "DENY", "reason": auth.get("reason", "NOT_AUTHORIZED")}

    if not actor_id or not project_id or not acceptance_evidence_ref or not accepted_at:
        return {"decision": "HOLD", "reason": "CUSTOMER_ACCEPTANCE_EVIDENCE_REQUIRED"}
    if current_state != "QA_PASSED":
        return {"decision": "HOLD", "reason": "UAT_ACCEPTANCE_NOT_CURRENTLY_ELIGIBLE"}
    if not idempotency_key:
        return {"decision": "HOLD", "reason": "IDEMPOTENCY_KEY_REQUIRED"}

    authority = LIFECYCLE.AuthorityReceipt(
        org_id=resource_org,
        actor_id=actor_id,
        approved_at=accepted_at,
        human_approved=False,
        evidence_refs=(acceptance_evidence_ref,),
        idempotency_key=idempotency_key,
    )
    transition = LIFECYCLE.TransitionRequest(
        org_id=resource_org,
        from_state="QA_PASSED",
        to_state="CUSTOMER_ACCEPTED",
        evidence=frozenset({"customer_acceptance_evidence"}),
        dependencies={},
        authority=authority,
        stale_or_contradictory=False,
        material_scope_change=False,
        change_request_approved=False,
    )
    result = LIFECYCLE.evaluate_transition(transition, consumed_keys=consumed_keys)
    if result.get("status") == "IDEMPOTENT_REPLAY":
        return {
            "decision": "IDEMPOTENT_REPLAY",
            "reason": result["reason"],
            "source_truth_mutated": False,
        }
    if result.get("status") != "PASS":
        return {
            "decision": "HOLD",
            "reason": result.get("reason", "LIFECYCLE_GATE_HOLD"),
            "source_truth_mutated": False,
        }

    receipt = {
        "schema": "lds.customer-uat-acceptance-intake/1",
        "project_id": project_id,
        "org_id": resource_org,
        "actor_id": actor_id,
        "accepted_at": accepted_at,
        "acceptance_evidence_ref": acceptance_evidence_ref,
        "from_state": "QA_PASSED",
        "to_state": "CUSTOMER_ACCEPTED",
        "idempotency_key": idempotency_key,
        "lifecycle_receipt_digest": result["receipt_digest"],
    }
    return {
        "decision": "ALLOW",
        "gateway_schema": SCHEMA,
        "handoff": "LD_INTEGRATED_CUSTOMER_LIFECYCLE_GATE",
        "handoff_state": "READY_FOR_AUTHORITATIVE_COMMIT",
        "receipt": receipt,
        "receipt_digest": _digest(receipt),
        "source_truth_mutated": False,
        "production_authority": "NONE",
        "payment_authority": "NONE",
        "pricing_authority": "NONE",
    }


def route_customer_action(action: str, **kwargs: Any) -> dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        return {
            "decision": "HOLD",
            "reason": "CUSTOMER_ACTION_UNSUPPORTED",
            "supported_actions": sorted(ALLOWED_ACTIONS),
        }
    if action == "REQUEST_CHANGE":
        return request_change(**kwargs)
    return accept_uat(**kwargs)


def gateway_can_mutate_authoritative_state() -> bool:
    return False
