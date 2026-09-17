import json
import unittest
from pathlib import Path

from portfolio_truth_bridge import (
    build_portfolio_director_view,
    build_project_truth_snapshot,
    validate_source_registry,
)

ROOT = Path(__file__).resolve().parent


def registry_fixture():
    return {
        "version": "2.0",
        "sources": [
            {
                "project_id": "ebkl",
                "name": "e-BKL",
                "objective_id": "portfolio:ebkl:readiness",
                "repository": "lundus88/ebkl",
                "default_branch": "main",
                "mode": "READ_ONLY",
            },
            {
                "project_id": "urusmy",
                "name": "UrusMY",
                "objective_id": "portfolio:urusmy:readiness",
                "repository": "lundus88/urusmy",
                "default_branch": "main",
                "mode": "READ_ONLY",
            },
            {
                "project_id": "slp",
                "name": "Spatial & Land Planner (SLP)",
                "objective_id": "portfolio:slp:readiness",
                "repository": None,
                "default_branch": None,
                "mode": "UNREGISTERED_HOLD",
                "hold_reason": "AUTHORITATIVE_SOURCE_NOT_REGISTERED",
            },
        ],
    }


def observations_fixture():
    return {
        "schema": "lom.portfolio-observation/2",
        "captured_at": "1970-01-01T00:16:40Z",
        "mode": "READ_ONLY_FAIL_CLOSED",
        "production_authority": "HUMAN_ONLY",
        "observations": [
            {
                "project_id": "ebkl",
                "repository": "lundus88/ebkl",
                "accessible": True,
                "default_branch": "main",
                "main_sha": "abc123",
                "signals": ["MAIN_ACTIVE"],
                "evidence_refs": ["commit:abc123"],
            }
        ],
    }


class PortfolioTruthBridgeTests(unittest.TestCase):
    def test_real_registry_contains_expected_portfolio_projects(self):
        registry = json.loads((ROOT / "source-registry.json").read_text(encoding="utf-8"))
        project_ids = {item["project_id"] for item in validate_source_registry(registry)}
        self.assertTrue({"vl", "ebkl", "sabahlot", "slp", "lunduslead", "urusmy", "kontenstudio"}.issubset(project_ids))

    def test_repository_evidence_never_self_promotes_to_verified(self):
        snapshot = build_project_truth_snapshot(registry_fixture(), observations_fixture(), 1100, 500)
        by_id = {item["project_id"]: item for item in snapshot["projects"]}
        self.assertEqual(by_id["ebkl"]["status"], "UNVERIFIED")
        self.assertNotIn("VERIFIED", {item["status"] for item in snapshot["projects"]})

    def test_missing_and_unregistered_sources_hold(self):
        snapshot = build_project_truth_snapshot(registry_fixture(), observations_fixture(), 1100, 500)
        by_id = {item["project_id"]: item for item in snapshot["projects"]}
        self.assertEqual(by_id["urusmy"]["status"], "HOLD")
        self.assertEqual(by_id["slp"]["status"], "HOLD")
        bindings = {item["project_id"]: item for item in snapshot["portfolio_binding"]["projects"]}
        self.assertEqual(bindings["slp"]["binding_reason"], "AUTHORITATIVE_SOURCE_NOT_REGISTERED")
        self.assertIsNone(bindings["slp"]["repository"])

    def test_stale_repository_evidence_holds(self):
        snapshot = build_project_truth_snapshot(registry_fixture(), observations_fixture(), 2000, 500)
        ebkl = next(item for item in snapshot["projects"] if item["project_id"] == "ebkl")
        self.assertEqual(ebkl["status"], "HOLD")
        self.assertEqual(ebkl["reason"], "STALE_EVIDENCE")

    def test_director_view_exposes_full_catalog_and_holds_unready_projects(self):
        view = build_portfolio_director_view(registry_fixture(), observations_fixture(), 1100, max_observation_age_seconds=500)
        self.assertEqual(view["schema_version"], 3)
        self.assertEqual(view["overall_action_class"], "HOLD")
        self.assertEqual(view["portfolio"]["registered_project_count"], 3)
        self.assertEqual(view["portfolio"]["truth_unready_catalog_count"], 3)
        project_ids = {item["project_id"] for item in view["project_truth"]["projects"]}
        self.assertEqual(project_ids, {"ebkl", "urusmy", "slp"})
        self.assertEqual(view["production_authority"], "HUMAN_ONLY")
        self.assertEqual(view["protected_main_merge"], "HUMAN_ONLY")
        self.assertEqual(view["control_execution"], "DISABLED")

    def test_duplicate_project_id_is_rejected(self):
        registry = registry_fixture()
        registry["sources"].append(dict(registry["sources"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PROJECT_ID"):
            validate_source_registry(registry)

    def test_unregistered_source_cannot_invent_repository(self):
        registry = registry_fixture()
        registry["sources"][2]["repository"] = "lundus88/invented-slp"
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_SOURCE_MUST_NOT_INVENT_REPOSITORY"):
            validate_source_registry(registry)

    def test_truth_snapshot_preserves_authority_boundary(self):
        snapshot = build_project_truth_snapshot(registry_fixture(), observations_fixture(), 1100, 500)
        self.assertEqual(snapshot["autonomous_ceiling"], "PREPARE_PR")
        self.assertEqual(snapshot["production_authority"], "HUMAN_ONLY")
        self.assertEqual(snapshot["protected_main_merge"], "HUMAN_ONLY")
        self.assertEqual(snapshot["execution_authority"], "NONE")
        self.assertFalse(snapshot["execution_performed"])


if __name__ == "__main__":
    unittest.main()
