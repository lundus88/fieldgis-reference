import unittest

from evidence_capture import begin_capture, finalize_capture, sha256_json


def envelope():
    return begin_capture(
        run_id="gw-verified-001",
        project_id="lom",
        request_id="req-001",
        app_spec={"objective": "validate governed workflow"},
        context_policy={"environment": "NON_PRODUCTION", "authority": "PREPARE_PR"},
        model_routing_decision={"model": "test", "reason": "bounded"},
        capability_scope=["repo.read", "ci.inspect", "pr.prepare"],
        resource_scope=["repo:lundus88/fieldgis-reference"],
        token_budget=10000,
        cost_budget=5.0,
        time_budget_seconds=900,
        retry_budget=2,
        source_commit_sha="a" * 40,
    )


def complete(**kw):
    args = dict(
        artifact_bytes=b"artifact-v1",
        qa_security_evidence=[{"kind": "ci", "status": "SUCCESS", "ref": "run-1"}],
        independent_validation={"actor": "validator", "status": "PASS"},
        remediation_history=[],
        release_candidate_state="RC_READY",
        human_decision="APPROVED_FOR_MERGE",
        release_outcome="MERGED_NON_PRODUCTION_CODE_ONLY",
        rollback_audit_linkage="audit://gw-verified-001",
        final_outcome="PASS",
        attempts=1,
        elapsed_seconds=120,
        estimated_model_tool_cost=1.0,
        production_approval=False,
        builder_self_certified=False,
        authority_expansion_incident=False,
        fabricated_pass_incident=False,
        multi_agent_delegation={"demonstrated": True, "authority_expanded": False},
    )
    args.update(kw)
    return finalize_capture(envelope(), **args)


class EvidenceCaptureTests(unittest.TestCase):
    def test_complete_safe_capture_is_verified(self):
        result = complete()
        self.assertEqual(result["evidence_state"], "VERIFIED")
        self.assertTrue(result["promotion_allowed"])
        self.assertTrue(result["production_locked"])
        self.assertEqual(result["autonomous_ceiling"], "PREPARE_PR")

    def test_digest_is_deterministic(self):
        self.assertEqual(
            sha256_json({"b": 2, "a": 1}),
            sha256_json({"a": 1, "b": 2}),
        )

    def test_missing_independent_validation_is_partial(self):
        result = complete(independent_validation=None)
        self.assertEqual(result["evidence_state"], "PARTIAL")
        self.assertIn(
            "INDEPENDENT_VALIDATION_REQUIRED", result["capture_errors"]
        )

    def test_missing_human_decision_is_partial(self):
        result = complete(human_decision=None)
        self.assertEqual(result["evidence_state"], "PARTIAL")
        self.assertIn("HUMAN_DECISION_REQUIRED", result["capture_errors"])

    def test_budget_overrun_cannot_verify(self):
        result = complete(estimated_model_tool_cost=6.0)
        self.assertEqual(result["evidence_state"], "PARTIAL")
        self.assertIn("BUDGET_OVERRUN_FORBIDDEN", result["capture_errors"])

    def test_production_approval_cannot_verify(self):
        result = complete(production_approval=True)
        self.assertEqual(result["evidence_state"], "PARTIAL")
        self.assertIn(
            "AUTONOMOUS_PRODUCTION_APPROVAL_FORBIDDEN",
            result["capture_errors"],
        )

    def test_builder_self_certification_cannot_verify(self):
        result = complete(builder_self_certified=True)
        self.assertEqual(result["evidence_state"], "PARTIAL")
        self.assertIn(
            "BUILDER_SELF_CERTIFICATION_FORBIDDEN",
            result["capture_errors"],
        )

    def test_authority_expansion_cannot_verify(self):
        result = complete(
            multi_agent_delegation={
                "demonstrated": True,
                "authority_expanded": True,
            }
        )
        self.assertEqual(result["evidence_state"], "PARTIAL")
        self.assertIn(
            "DELEGATION_AUTHORITY_EXPANSION_FORBIDDEN",
            result["capture_errors"],
        )


if __name__ == "__main__":
    unittest.main()
