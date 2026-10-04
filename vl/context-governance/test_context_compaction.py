import copy
import json
import unittest
from pathlib import Path

from context_compaction import compact_allowed_context, validate_compaction_manifest
from pre_model_invocation import ContextGovernanceBlocked, build_pre_model_payload

ROOT = Path(__file__).resolve().parent


class ContextCompactionTests(unittest.TestCase):
    def test_small_context_passes_through_without_abstractive_summary(self):
        allowed = [
            {
                "resource_type": "repo_path",
                "resource": "src/a.py",
                "data_class": "source_code",
                "content": "def a():\n    return 1\n",
            }
        ]
        out = compact_allowed_context(
            allowed,
            task={"objective": "inspect a"},
            max_context_chars=1000,
        )
        self.assertEqual(out["status"], "READY")
        self.assertFalse(out["manifest"]["compacted"])
        self.assertFalse(out["manifest"]["abstractive_summary_generated"])
        self.assertEqual(validate_compaction_manifest(out["manifest"])["status"], "READY")

    def test_large_context_is_extractive_and_task_relevant(self):
        allowed = [
            {
                "resource_type": "repo_path",
                "resource": "src/a.py",
                "data_class": "source_code",
                "content": (
                    "header line\n"
                    "unrelated alpha beta gamma\n"
                    "target_function handles cadastral evidence safely\n"
                    "tail line\n"
                ),
            },
            {
                "resource_type": "repo_path",
                "resource": "tests/test_a.py",
                "data_class": "test_code",
                "content": (
                    "test header\n"
                    "test target_function evidence path\n"
                    "test tail\n"
                ),
            },
        ]
        out = compact_allowed_context(
            allowed,
            task={"objective": "fix target_function evidence"},
            max_context_chars=100,
            chunk_chars=55,
        )
        self.assertEqual(out["status"], "READY")
        self.assertTrue(out["manifest"]["compacted"])
        self.assertEqual(out["manifest"]["selected_resource_count"], 2)
        self.assertEqual(out["manifest"]["dropped_resource_count"], 0)
        encoded = json.dumps(out)
        self.assertIn("target_function", encoded)
        self.assertLessEqual(
            out["manifest"]["selected_char_count"],
            out["manifest"]["max_context_chars"],
        )
        self.assertEqual(validate_compaction_manifest(out["manifest"])["status"], "READY")

    def test_budget_too_small_for_resource_coverage_fails_closed(self):
        allowed = [
            {
                "resource_type": "repo_path",
                "resource": "src/a.py",
                "data_class": "source_code",
                "content": "A" * 50,
            },
            {
                "resource_type": "repo_path",
                "resource": "tests/test_a.py",
                "data_class": "test_code",
                "content": "B" * 50,
            },
        ]
        out = compact_allowed_context(
            allowed,
            task={"objective": "test"},
            max_context_chars=30,
            chunk_chars=30,
        )
        self.assertEqual(out["status"], "HOLD")
        self.assertEqual(
            out["reason"],
            "CONTEXT_BUDGET_INSUFFICIENT_FOR_RESOURCE_COVERAGE",
        )

    def test_compaction_is_deterministic_across_resource_order(self):
        a = {
            "resource_type": "repo_path",
            "resource": "src/a.py",
            "data_class": "source_code",
            "content": "one\ntarget here\nthree\n",
        }
        b = {
            "resource_type": "repo_path",
            "resource": "tests/a.py",
            "data_class": "test_code",
            "content": "test one\ntarget test\ntest three\n",
        }
        x = compact_allowed_context(
            [a, b],
            task={"objective": "target"},
            max_context_chars=45,
            chunk_chars=24,
        )
        y = compact_allowed_context(
            [b, a],
            task={"objective": "target"},
            max_context_chars=45,
            chunk_chars=24,
        )
        self.assertEqual(
            x["manifest"]["compaction_digest"],
            y["manifest"]["compaction_digest"],
        )
        self.assertEqual(x["context"], y["context"])

    def test_manifest_tamper_is_detected(self):
        allowed = [{
            "resource_type": "repo_path",
            "resource": "src/a.py",
            "data_class": "source_code",
            "content": "safe",
        }]
        out = compact_allowed_context(
            allowed,
            task={"objective": "safe"},
            max_context_chars=50,
        )
        tampered = copy.deepcopy(out["manifest"])
        tampered["selected_char_count"] = 999
        self.assertEqual(
            validate_compaction_manifest(tampered)["reason"],
            "CONTEXT_COMPACTION_DIGEST_MISMATCH",
        )

    def test_pre_model_boundary_filters_secret_before_compaction(self):
        resources = [
            {
                "resource_type": "repo_path",
                "resource": "src/app.ts",
                "data_class": "source_code",
                "content": "target logic\n" + ("safe line\n" * 20),
            },
            {
                "resource_type": "repo_path",
                "resource": "src/.env.production",
                "data_class": "secret",
                "content": "TOP_SECRET_VALUE",
            },
        ]
        payload = build_pre_model_payload(
            policy_path=ROOT / "default-context-policy.json",
            resources=resources,
            task={"objective": "inspect target logic"},
            max_context_chars=80,
            compaction_chunk_chars=40,
        )
        encoded = json.dumps(payload, sort_keys=True)
        self.assertNotIn("TOP_SECRET_VALUE", encoded)
        self.assertTrue(payload["context_compacted"])
        self.assertFalse(payload["raw_candidates_forwarded"])
        self.assertEqual(
            validate_compaction_manifest(payload["context_compaction_manifest"])["status"],
            "READY",
        )

    def test_pre_model_boundary_holds_when_budget_cannot_cover_allowed_resources(self):
        resources = [
            {
                "resource_type": "repo_path",
                "resource": "src/a.ts",
                "data_class": "source_code",
                "content": "A" * 80,
            },
            {
                "resource_type": "repo_path",
                "resource": "src/b.ts",
                "data_class": "source_code",
                "content": "B" * 80,
            },
        ]
        with self.assertRaisesRegex(
            ContextGovernanceBlocked,
            "CONTEXT_COMPACTION_BLOCKED",
        ):
            build_pre_model_payload(
                policy_path=ROOT / "default-context-policy.json",
                resources=resources,
                task={"objective": "inspect"},
                max_context_chars=20,
                compaction_chunk_chars=20,
            )


if __name__ == "__main__":
    unittest.main()
