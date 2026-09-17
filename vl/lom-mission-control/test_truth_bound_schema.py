import json
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCHEMA = json.loads((HERE / "mission-control-view-v3.schema.json").read_text(encoding="utf-8"))


class TruthBoundSchemaTests(unittest.TestCase):
    def test_schema_version_is_v3(self):
        self.assertEqual(SCHEMA["properties"]["schema_version"]["const"], 3)

    def test_project_truth_is_required(self):
        self.assertIn("project_truth", SCHEMA["required"])
        self.assertIn("project_status_authority", SCHEMA["required"])

    def test_project_status_authority_is_canonical_truth(self):
        self.assertEqual(
            SCHEMA["properties"]["project_status_authority"]["const"],
            "LOM_6_10_PROJECT_STATE_TRUTH",
        )

    def test_authority_boundaries_are_locked(self):
        self.assertEqual(SCHEMA["properties"]["autonomous_ceiling"]["const"], "PREPARE_PR")
        self.assertEqual(SCHEMA["properties"]["control_execution"]["const"], "DISABLED")
        self.assertEqual(SCHEMA["properties"]["production_authority"]["const"], "HUMAN_ONLY")
        self.assertEqual(SCHEMA["properties"]["protected_main_merge"]["const"], "HUMAN_ONLY")
        truth = SCHEMA["properties"]["project_truth"]["properties"]
        self.assertEqual(truth["execution_authority"]["const"], "NONE")
        self.assertFalse(truth["execution_performed"]["const"])


if __name__ == "__main__":
    unittest.main()
