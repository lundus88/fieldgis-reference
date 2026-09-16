import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
VL = HERE.parent

spec = importlib.util.spec_from_file_location("project_state_truth", HERE / "project_state_truth.py")
project_state_truth = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = project_state_truth
spec.loader.exec_module(project_state_truth)

ledger_spec = importlib.util.spec_from_file_location(
    "event_ledger",
    VL / "lom-operational-safety" / "event_ledger.py",
)
event_ledger = importlib.util.module_from_spec(ledger_spec)
sys.modules[ledger_spec.name] = event_ledger
ledger_spec.loader.exec_module(event_ledger)

EvidenceRecord = project_state_truth.EvidenceRecord
EvidenceRegistry = project_state_truth.EvidenceRegistry
ProjectObservation = project_state_truth.ProjectObservation
ProjectStateTruthGraph = project_state_truth.ProjectStateTruthGraph
AppendOnlyEventLedger = event_ledger.AppendOnlyEventLedger


class ProjectStateTruthTests(unittest.TestCase):
    def setUp(self):
        self.registry = EvidenceRegistry()
        self.ledger = AppendOnlyEventLedger()
        self.event = self.ledger.append(
            "run-1",
            "obj-1",
            "validator",
            "RUN_TEST",
            ["ev-1"],
            "VALIDATING",
            "COMPLETE",
            "validated",
            1000,
        )
        self.graph = ProjectStateTruthGraph(self.registry, self.ledger)

    def evidence(self, **overrides):
        data = dict(
            evidence_id="ev-1",
            project_id="ebkl",
            objective_id="obj-1",
            evidence_type="CI",
            result="PASS",
            source_reference="ci://ebkl/run/1",
            observed_at_epoch=1000,
            expires_at_epoch=2000,
            actor_id="validator",
            independent=True,
            human_approval=False,
            contradictory=False,
            ledger_event_hash=self.event["event_hash"],
        )
        data.update(overrides)
        return EvidenceRecord(**data)

    def observation(self, **overrides):
        data = dict(
            project_id="ebkl",
            objective_id="obj-1",
            state="VERIFIED",
            evidence_ids=("ev-1",),
            observed_at_epoch=1000,
        )
        data.update(overrides)
        return ProjectObservation(**data)

    def test_clean_verified_state_is_evidence_bound(self):
        self.registry.register(self.evidence())
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["status"], "VERIFIED")
        self.assertEqual(snapshot["projects"][0]["reason"], "EVIDENCE_BOUND_STATE")

    def test_verified_requires_independent_validation(self):
        self.registry.register(self.evidence(independent=False))
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "INDEPENDENT_VALIDATION_REQUIRED")

    def test_approved_requires_approval_evidence(self):
        self.registry.register(self.evidence())
        snapshot = self.graph.build_snapshot([self.observation(state="APPROVED")], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "HUMAN_APPROVAL_EVIDENCE_REQUIRED")

    def test_production_release_requires_human_approval(self):
        self.registry.register(self.evidence())
        snapshot = self.graph.build_snapshot([self.observation(state="RELEASED", production=True)], 1200)
        self.assertEqual(snapshot["projects"][0]["status"], "HOLD")

    def test_production_release_can_be_observed_when_evidence_and_human_approval_exist(self):
        self.registry.register(self.evidence(human_approval=True, result="APPROVED"))
        snapshot = self.graph.build_snapshot([self.observation(state="RELEASED", production=True)], 1200)
        self.assertEqual(snapshot["projects"][0]["status"], "RELEASED")
        self.assertEqual(snapshot["production_authority"], "HUMAN_ONLY")
        self.assertFalse(snapshot["execution_performed"])

    def test_stale_evidence_holds(self):
        self.registry.register(self.evidence(expires_at_epoch=1100))
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "STALE_EVIDENCE")

    def test_contradictory_evidence_holds(self):
        self.registry.register(self.evidence(contradictory=True))
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "CONTRADICTORY_EVIDENCE")

    def test_evidence_must_be_ledger_bound(self):
        self.registry.register(self.evidence(ledger_event_hash="not-in-ledger"))
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "EVIDENCE_NOT_LEDGER_BOUND")

    def test_cross_scope_evidence_holds(self):
        self.registry.register(self.evidence(project_id="sabahlot"))
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "EVIDENCE_SCOPE_MISMATCH")

    def test_unregistered_evidence_holds(self):
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "UNREGISTERED_EVIDENCE")

    def test_fail_evidence_blocks(self):
        self.registry.register(self.evidence(result="FAIL"))
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["status"], "FAILED")

    def test_duplicate_identical_evidence_is_idempotent(self):
        record = self.evidence()
        self.registry.register(record)
        self.registry.register(record)
        self.assertEqual(self.registry.get("ev-1"), record)

    def test_evidence_id_collision_rejected(self):
        self.registry.register(self.evidence())
        with self.assertRaisesRegex(ValueError, "EVIDENCE_ID_COLLISION"):
            self.registry.register(self.evidence(result="FAIL"))

    def test_registry_is_immutable(self):
        with self.assertRaisesRegex(RuntimeError, "IMMUTABLE_EVIDENCE_REGISTRY"):
            self.registry.replace()
        with self.assertRaisesRegex(RuntimeError, "IMMUTABLE_EVIDENCE_REGISTRY"):
            self.registry.delete()

    def test_invalid_ledger_holds_entire_graph(self):
        self.registry.register(self.evidence())
        self.ledger._events[0]["event_hash"] = "tampered"
        snapshot = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "LEDGER_INTEGRITY_FAILED")

    def test_record_digest_tamper_rejected(self):
        self.registry.register(self.evidence())
        with self.assertRaisesRegex(ValueError, "EVIDENCE_ID_COLLISION"):
            self.registry.register(self.evidence(source_reference="ci://different"))

    def test_conflicting_latest_observations_hold(self):
        self.registry.register(self.evidence())
        items = [self.observation(), self.observation(state="APPROVED")]
        snapshot = self.graph.build_snapshot(items, 1200)
        self.assertEqual(snapshot["projects"][0]["reason"], "CONFLICTING_PROJECT_OBSERVATIONS")

    def test_dependency_blockage_propagates_hold(self):
        second_event = self.ledger.append(
            "run-2", "obj-2", "validator", "RUN_TEST", ["ev-2"], "VALIDATING", "COMPLETE", "validated", 1001
        )
        self.registry.register(self.evidence())
        self.registry.register(
            EvidenceRecord(
                evidence_id="ev-2",
                project_id="sabahlot",
                objective_id="obj-2",
                evidence_type="CI",
                result="PASS",
                source_reference="ci://sabahlot/run/2",
                observed_at_epoch=1001,
                expires_at_epoch=2000,
                actor_id="validator",
                independent=True,
                ledger_event_hash=second_event["event_hash"],
            )
        )
        ebkl = self.observation(state="HOLD")
        sabahlot = ProjectObservation(
            project_id="sabahlot",
            objective_id="obj-2",
            state="VERIFIED",
            evidence_ids=("ev-2",),
            observed_at_epoch=1001,
            dependencies=("ebkl",),
        )
        snapshot = self.graph.build_snapshot([ebkl, sabahlot], 1200)
        sabah_state = next(item for item in snapshot["projects"] if item["project_id"] == "sabahlot")
        self.assertEqual(sabah_state["reason"], "DEPENDENCY_NOT_READY")

    def test_snapshot_fingerprint_is_deterministic(self):
        self.registry.register(self.evidence())
        one = self.graph.build_snapshot([self.observation()], 1200)
        two = self.graph.build_snapshot([self.observation()], 1200)
        self.assertEqual(one["snapshot_fingerprint"], two["snapshot_fingerprint"])


if __name__ == "__main__":
    unittest.main()
