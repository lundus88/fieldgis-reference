import json
import unittest
from governed_dryrun import run_dryrun


class GovernedDryRunTests(unittest.TestCase):
    def test_full_dryrun_is_nonproduction_and_fail_closed(self):
        result = run_dryrun()
        self.assertEqual(result["status"], "READY_FOR_NONPRODUCTION_CONTROLLED_EXECUTION")
        self.assertTrue(result["production_locked"])
        self.assertFalse(result["live_model_invocation"])
        self.assertFalse(result["live_connector_invocation"])
        self.assertFalse(result["live_execution"])
        self.assertFalse(result["merge_executed"])
        self.assertFalse(result["production_approved"])
        self.assertFalse(result["production_deployed"])
        self.assertEqual(result["context_governance"]["denied_count"], 1)
        self.assertEqual(result["completion"]["status"], "PASS")
        self.assertEqual(result["remediation"]["merge_prepare"], "ALLOW")
        self.assertEqual(result["remediation"]["merge_execute"], "DENY")
        self.assertEqual(result["connector"]["read"], "ALLOW")
        self.assertEqual(result["connector"]["high_impact_without_approval"], "DENY")
        self.assertEqual(result["execution_pool"]["decision"], "ALLOW")
        self.assertEqual(result["multi_agent"]["bounded_delegation"], "ALLOW")
        self.assertEqual(result["multi_agent"]["authority_expansion"], "DENY")

    def test_serialized_result_contains_no_secret_fixture(self):
        encoded = json.dumps(run_dryrun(), sort_keys=True)
        self.assertNotIn("NEVER_FORWARD_SECRET", encoded)
        self.assertNotIn("production.approve\": \"ALLOW", encoded)


if __name__ == "__main__":
    unittest.main()
