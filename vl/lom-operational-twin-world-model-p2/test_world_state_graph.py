import copy
import unittest

from world_state_graph import build_world_state_graph, validate_world_state_graph


def registry():
    return {
        "version": "2.0",
        "sources": [
            {
                "project_id": "vl",
                "name": "VL",
                "objective_id": "portfolio:vl:readiness",
                "repository": "lundus88/fieldgis-reference",
                "default_branch": "main",
                "mode": "READ_ONLY",
            },
            {
                "project_id": "ebkl",
                "name": "e-BKL",
                "objective_id": "portfolio:ebkl:readiness",
                "repository": "lundus88/ebkl",
                "default_branch": "main",
                "mode": "READ_ONLY",
            },
        ],
    }


def twin(project_id, status="READY", action_class="AUTO_PREPARE", reason="BOUNDED_NONPRODUCTION_PREPARATION_ELIGIBLE"):
    return {
        "schema": "lom.operational-twin/1",
        "status": status,
        "reason": reason,
        "project_id": project_id,
        "action_class": action_class,
        "next_action": "PREPARE_PR" if action_class == "AUTO_PREPARE" else "PREPARE_HUMAN_DECISION_PACKAGE",
        "snapshot_digest": "sha256:" + project_id.rjust(64, "0"),
        "autonomous_ceiling": "PREPARE_PR",
        "execution_authority": "NONE",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
    }


class WorldStateGraphTests(unittest.TestCase):
    def test_ready_graph_is_deterministic_and_read_only(self):
        deps = [{
            "downstream_project_id": "ebkl",
            "upstream_project_id": "vl",
            "evidence_ref": "urn:lom:dependency:ebkl:vl",
        }]
        a = build_world_state_graph(registry(), [twin("vl"), twin("ebkl")], dependencies=deps)
        b = build_world_state_graph(registry(), [twin("ebkl"), twin("vl")], dependencies=reversed(deps))
        self.assertEqual(a["status"], "READY")
        self.assertEqual(a["graph_digest"], b["graph_digest"])
        self.assertEqual(validate_world_state_graph(a)["status"], "READY")
        self.assertEqual(a["execution_authority"], "NONE")
        self.assertEqual(a["production_authority"], "HUMAN_ONLY")
        self.assertEqual(a["protected_main_merge"], "HUMAN_ONLY")
        self.assertEqual(a["database_mutation"], "DISABLED")
        self.assertEqual(a["connector_execution"], "DISABLED")

    def test_review_twin_surfaces_attention_without_rewriting_truth(self):
        g = build_world_state_graph(
            registry(),
            [
                twin("vl", status="REVIEW", action_class="HUMAN_REVIEW", reason="RISK_OR_REVERSIBILITY_REQUIRES_REVIEW"),
                twin("ebkl"),
            ],
            dependencies=[{
                "downstream_project_id": "ebkl",
                "upstream_project_id": "vl",
                "evidence_ref": "urn:lom:dependency:ebkl:vl",
            }],
        )
        self.assertEqual(g["status"], "READY")
        self.assertTrue(g["attention_required"])
        ebkl = next(n for n in g["nodes"] if n.get("node_id") == "project:ebkl")
        self.assertEqual(ebkl["dependency_attention_from"], ["vl"])
        self.assertTrue(ebkl["attention_required"])
        self.assertEqual(ebkl["twin_status"], "READY")

    def test_missing_twin_fails_closed(self):
        g = build_world_state_graph(registry(), [twin("vl")])
        self.assertEqual(g["status"], "HOLD")
        self.assertEqual(g["reason"], "OPERATIONAL_TWIN_COVERAGE_INCOMPLETE")
        self.assertIn("TWIN_MISSING:ebkl", g["violations"])

    def test_unknown_dependency_project_fails_closed(self):
        g = build_world_state_graph(
            registry(),
            [twin("vl"), twin("ebkl")],
            dependencies=[{
                "downstream_project_id": "ebkl",
                "upstream_project_id": "ghost",
                "evidence_ref": "urn:test",
            }],
        )
        self.assertEqual(g["status"], "HOLD")
        self.assertEqual(g["reason"], "DEPENDENCY_PROJECT_NOT_REGISTERED")

    def test_dependency_cycle_fails_closed(self):
        g = build_world_state_graph(
            registry(),
            [twin("vl"), twin("ebkl")],
            dependencies=[
                {
                    "downstream_project_id": "ebkl",
                    "upstream_project_id": "vl",
                    "evidence_ref": "urn:a",
                },
                {
                    "downstream_project_id": "vl",
                    "upstream_project_id": "ebkl",
                    "evidence_ref": "urn:b",
                },
            ],
        )
        self.assertEqual(g["status"], "HOLD")
        self.assertEqual(g["reason"], "DEPENDENCY_CYCLE_DETECTED")

    def test_unregistered_twin_project_fails_closed(self):
        g = build_world_state_graph(registry(), [twin("vl"), twin("ebkl"), twin("ghost")])
        self.assertEqual(g["status"], "HOLD")
        self.assertEqual(g["reason"], "TWIN_PROJECT_NOT_REGISTERED")

    def test_twin_cannot_weaken_authority(self):
        unsafe = twin("vl")
        unsafe["production_authority"] = "AUTONOMOUS"
        g = build_world_state_graph(registry(), [unsafe, twin("ebkl")])
        self.assertEqual(g["status"], "HOLD")
        self.assertEqual(g["reason"], "TWIN_PRODUCTION_AUTHORITY_WEAKENED")

    def test_digest_tampering_is_detected(self):
        g = build_world_state_graph(registry(), [twin("vl"), twin("ebkl")])
        tampered = copy.deepcopy(g)
        tampered["project_count"] = 99
        self.assertEqual(validate_world_state_graph(tampered)["reason"], "WORLD_GRAPH_DIGEST_MISMATCH")


if __name__ == "__main__":
    unittest.main()
