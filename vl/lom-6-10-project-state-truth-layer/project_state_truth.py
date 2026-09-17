from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable

OBSERVED_STATES = {
    "UNVERIFIED",
    "VERIFIED",
    "APPROVED",
    "RELEASED",
    "HOLD",
    "FAILED",
}

HUMAN_BOUND_STATES = {"APPROVED", "RELEASED"}
SUCCESS_EVIDENCE = {"PASS", "SUCCESS", "VERIFIED", "APPROVED"}
FAIL_EVIDENCE = {"FAIL", "FAILED", "ERROR", "REJECTED"}


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    project_id: str
    objective_id: str
    evidence_type: str
    result: str
    source_reference: str
    observed_at_epoch: int
    expires_at_epoch: int
    actor_id: str
    independent: bool = False
    human_approval: bool = False
    contradictory: bool = False
    ledger_event_hash: str | None = None


@dataclass(frozen=True)
class ProjectObservation:
    project_id: str
    objective_id: str
    state: str
    evidence_ids: tuple[str, ...]
    observed_at_epoch: int
    dependencies: tuple[str, ...] = ()
    production: bool = False


class EvidenceRegistry:
    """Immutable evidence registry keyed by evidence_id.

    Duplicate identical records are idempotent. Reuse of an evidence_id with
    different content is rejected to prevent silent evidence substitution.
    """

    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        self._digests: dict[str, str] = {}

    def register(self, record: EvidenceRecord) -> EvidenceRecord:
        if not record.evidence_id:
            raise ValueError("EVIDENCE_ID_REQUIRED")
        digest = _digest(record.__dict__)
        existing = self._digests.get(record.evidence_id)
        if existing is not None and existing != digest:
            raise ValueError("EVIDENCE_ID_COLLISION")
        self._records.setdefault(record.evidence_id, record)
        self._digests.setdefault(record.evidence_id, digest)
        return self._records[record.evidence_id]

    def get(self, evidence_id: str) -> EvidenceRecord | None:
        return self._records.get(evidence_id)

    def replace(self, *_args, **_kwargs) -> None:
        raise RuntimeError("IMMUTABLE_EVIDENCE_REGISTRY")

    def delete(self, *_args, **_kwargs) -> None:
        raise RuntimeError("IMMUTABLE_EVIDENCE_REGISTRY")


class ProjectStateTruthGraph:
    """Evidence-bound, fail-closed portfolio truth layer.

    This layer does not execute consequential actions. It derives a trusted
    observed state from immutable evidence and an independently verifiable
    append-only event ledger supplied by the caller.
    """

    def __init__(self, registry: EvidenceRegistry, ledger) -> None:
        self.registry = registry
        self.ledger = ledger

    def _ledger_hashes(self) -> set[str]:
        return {event.get("event_hash") for event in self.ledger.events}

    def _evidence_decision(
        self,
        observation: ProjectObservation,
        now_epoch: int,
    ) -> dict:
        if observation.state not in OBSERVED_STATES:
            return {"status": "HOLD", "reason": "UNKNOWN_PROJECT_STATE"}
        if not observation.project_id or not observation.objective_id:
            return {"status": "HOLD", "reason": "PROJECT_AND_OBJECTIVE_REQUIRED"}
        if not observation.evidence_ids:
            return {"status": "HOLD", "reason": "EVIDENCE_REQUIRED"}
        if not self.ledger.verify():
            return {"status": "HOLD", "reason": "LEDGER_INTEGRITY_FAILED"}

        ledger_hashes = self._ledger_hashes()
        records: list[EvidenceRecord] = []
        for evidence_id in observation.evidence_ids:
            record = self.registry.get(evidence_id)
            if record is None:
                return {"status": "HOLD", "reason": "UNREGISTERED_EVIDENCE"}
            if record.project_id != observation.project_id or record.objective_id != observation.objective_id:
                return {"status": "HOLD", "reason": "EVIDENCE_SCOPE_MISMATCH"}
            if not record.source_reference:
                return {"status": "HOLD", "reason": "EVIDENCE_PROVENANCE_REQUIRED"}
            if record.contradictory:
                return {"status": "HOLD", "reason": "CONTRADICTORY_EVIDENCE"}
            if record.expires_at_epoch < now_epoch:
                return {"status": "HOLD", "reason": "STALE_EVIDENCE"}
            if record.observed_at_epoch > now_epoch:
                return {"status": "HOLD", "reason": "FUTURE_EVIDENCE_TIMESTAMP"}
            if not record.ledger_event_hash or record.ledger_event_hash not in ledger_hashes:
                return {"status": "HOLD", "reason": "EVIDENCE_NOT_LEDGER_BOUND"}
            if record.result in FAIL_EVIDENCE:
                return {"status": "FAILED", "reason": "FAIL_EVIDENCE_PRESENT"}
            records.append(record)

        if not all(record.result in SUCCESS_EVIDENCE for record in records):
            return {"status": "HOLD", "reason": "EVIDENCE_RESULT_NOT_TRUSTED"}

        if observation.state in {"VERIFIED", "APPROVED", "RELEASED"} and not any(
            record.independent for record in records
        ):
            return {"status": "HOLD", "reason": "INDEPENDENT_VALIDATION_REQUIRED"}

        if observation.state in HUMAN_BOUND_STATES and not any(record.human_approval for record in records):
            return {"status": "HOLD", "reason": "HUMAN_APPROVAL_EVIDENCE_REQUIRED"}

        if observation.production and observation.state == "RELEASED" and not any(
            record.human_approval for record in records
        ):
            return {"status": "HOLD", "reason": "PRODUCTION_RELEASE_HUMAN_ONLY"}

        return {"status": observation.state, "reason": "EVIDENCE_BOUND_STATE"}

    def build_snapshot(
        self,
        observations: Iterable[ProjectObservation],
        now_epoch: int,
    ) -> dict:
        items = list(observations)
        by_project = {item.project_id: item for item in items}
        decisions: dict[str, dict] = {}

        # Reject contradictory latest observations for the same project.
        if len(by_project) != len(items):
            duplicate_projects = {item.project_id for item in items if sum(x.project_id == item.project_id for x in items) > 1}
            for project_id in duplicate_projects:
                decisions[project_id] = {"status": "HOLD", "reason": "CONFLICTING_PROJECT_OBSERVATIONS"}

        for item in items:
            if item.project_id in decisions:
                continue
            decisions[item.project_id] = self._evidence_decision(item, now_epoch)

        # Dependency failure/hold propagates fail-closed to dependants.
        changed = True
        while changed:
            changed = False
            for item in items:
                current = decisions[item.project_id]
                if current["status"] in {"HOLD", "FAILED"}:
                    continue
                for dependency in item.dependencies:
                    dependency_state = decisions.get(dependency)
                    if dependency_state is None or dependency_state["status"] in {"HOLD", "FAILED", "UNVERIFIED"}:
                        decisions[item.project_id] = {
                            "status": "HOLD",
                            "reason": "DEPENDENCY_NOT_READY",
                            "dependency": dependency,
                        }
                        changed = True
                        break

        projects = [
            {
                "project_id": project_id,
                **decision,
            }
            for project_id, decision in sorted(decisions.items())
        ]
        fingerprint = _digest(projects)
        overall = "MONITOR"
        if any(item["status"] == "FAILED" for item in projects):
            overall = "FAILED"
        elif any(item["status"] == "HOLD" for item in projects):
            overall = "HOLD"

        return {
            "schema": "lom.project-state-truth/1",
            "mode": "READ_ONLY_NON_PRODUCTION",
            "overall": overall,
            "projects": projects,
            "snapshot_fingerprint": fingerprint,
            "autonomous_ceiling": "PREPARE_PR",
            "protected_main_merge": "HUMAN_ONLY",
            "production_authority": "HUMAN_ONLY",
            "execution_authority": "NONE",
            "execution_performed": False,
        }
