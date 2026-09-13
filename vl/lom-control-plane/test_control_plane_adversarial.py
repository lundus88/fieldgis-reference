#!/usr/bin/env python3
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text())


class TestLOMControlPlaneAdversarial(unittest.TestCase):
    def setUp(self):
        self.portfolio = load("portfolio-registry.schema.json")
        self.evidence = load("evidence-record.schema.json")
        self.authority = load("authority-matrix.json")
        self.exceptions = load("exception-queue.schema.json")

    def test_unknown_authority_fails_closed(self):
        self.assertEqual(self.authority["default_decision"], "DENY_OR_HOLD")
        self.assertFalse(self.authority["invariants"]["unknown_authority_allowed"])

    def test_production_actions_are_human_gated(self):
        rules = {r["action"]: r for r in self.authority["rules"]}
        for action in (
            "MERGE_PROTECTED_MAIN",
            "PRODUCTION_DEPLOY",
            "PRODUCTION_DATA_MUTATION",
            "PRODUCTION_AUTHORITY_CHANGE",
            "FINANCIAL_OR_CONTRACTUAL_COMMITMENT",
        ):
            self.assertEqual(rules[action]["authority"], "HUMAN_APPROVAL")
            self.assertTrue(rules[action]["evidence_required"])

    def test_builder_self_certification_prohibited(self):
        self.assertFalse(self.authority["invariants"]["builder_self_certification_allowed"])
        rules = {r["action"]: r for r in self.authority["rules"]}
        self.assertEqual(rules["INDEPENDENT_CERTIFICATION"]["authority"], "AUTO_SEPARATE_ROLE")

    def test_delegation_cannot_widen_scope(self):
        self.assertFalse(self.authority["invariants"]["delegation_may_widen_scope"])

    def test_release_candidate_requires_evidence_and_approval(self):
        project = self.portfolio["$defs"]["project"]
        matched = []
        for rule in project.get("allOf", []):
            condition = rule.get("if", {}).get("properties", {}).get("health", {}).get("const")
            if condition == "RELEASE_CANDIDATE":
                matched.append(rule)
        self.assertEqual(len(matched), 1)
        then = matched[0]["then"]
        self.assertIn("evidence_refs", then["required"])
        self.assertIn("approval_required", then["required"])
        self.assertTrue(then["properties"]["approval_required"]["const"])

    def test_positive_claims_have_evidence_classes(self):
        types = set(self.evidence["properties"]["evidence_type"]["enum"])
        for required in ("QA", "SECURITY", "CERTIFICATION", "APPROVAL", "RELEASE", "AUDIT"):
            self.assertIn(required, types)
        self.assertIn("actor", self.evidence["required"])
        self.assertIn("source", self.evidence["required"])

    def test_exception_queue_supports_management_by_exception(self):
        categories = set(self.exceptions["$defs"]["exception"]["properties"]["category"]["enum"])
        for required in (
            "HUMAN_APPROVAL",
            "AUTHORITY_GAP",
            "EVIDENCE_GAP",
            "RISK_THRESHOLD",
            "UNRESOLVED_BLOCKER",
            "PRODUCTION_TRANSITION",
            "CONFLICTING_EVIDENCE",
        ):
            self.assertIn(required, categories)


if __name__ == "__main__":
    unittest.main(verbosity=2)
