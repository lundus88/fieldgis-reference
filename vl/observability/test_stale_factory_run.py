import unittest
from datetime import datetime, timezone

from classify_stale_factory_run import blocked_event, classify


NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
STALE = 3600


def run_fixture(**overrides):
    base = {
        "id": "cd2ae968-ccd4-4222-b140-ed463dc72fbb",
        "project_id": "historical-project",
        "state": "validating",
        "started_at": "2026-08-31T08:57:54+00:00",
        "runner_status": "PASS",
        "runner_qa_result": "PASS",
        "deployment_count": 0,
        "workflow_state": "running",
        "default_environments_present": False,
    }
    base.update(overrides)
    return base


class StaleFactoryRunTests(unittest.TestCase):
    def test_historical_orphan_candidate_matches_known_pattern(self):
        d = classify(run_fixture(), now=NOW, stale_after_seconds=STALE)
        self.assertEqual(d["classification"], "HISTORICAL_ORPHAN_CANDIDATE")
        self.assertFalse(d["mutation_performed"])
        self.assertFalse(d["production_authority"])

    def test_current_path_same_pattern_requires_review_not_auto_cleanup(self):
        d = classify(run_fixture(id="current-run", default_environments_present=True), now=NOW, stale_after_seconds=STALE)
        self.assertEqual(d["classification"], "CURRENT_PATH_REGRESSION_REQUIRES_REVIEW")
        self.assertFalse(d["mutation_performed"])

    def test_fresh_validating_run_is_not_orphan(self):
        d = classify(run_fixture(started_at="2026-09-06T11:45:00+00:00"), now=NOW, stale_after_seconds=STALE)
        self.assertEqual(d["classification"], "NO_ACTION")

    def test_failed_runner_is_not_historical_orphan_pattern(self):
        d = classify(run_fixture(runner_status="FAIL", runner_qa_result="FAIL"), now=NOW, stale_after_seconds=STALE)
        self.assertEqual(d["classification"], "NO_ACTION")

    def test_existing_deployment_is_not_orphan_pattern(self):
        d = classify(run_fixture(deployment_count=1), now=NOW, stale_after_seconds=STALE)
        self.assertEqual(d["classification"], "NO_ACTION")

    def test_missing_fields_fail_to_review_required(self):
        r = run_fixture()
        del r["workflow_state"]
        d = classify(r, now=NOW, stale_after_seconds=STALE)
        self.assertEqual(d["classification"], "REVIEW_REQUIRED")
        self.assertEqual(d["reason_code"], "MISSING_OBSERVABILITY_FIELDS")

    def test_threshold_is_explicit_not_hidden_business_rule(self):
        with self.assertRaises(ValueError):
            classify(run_fixture(), now=NOW, stale_after_seconds=0)

    def test_blocked_event_is_machine_readable_and_non_mutating(self):
        d = classify(run_fixture(), now=NOW, stale_after_seconds=STALE)
        event = blocked_event(factory_run_id=d["factory_run_id"], reason_code="RELEASE_CANDIDATE_BLOCKED", source_decision=d)
        self.assertEqual(event["event_type"], "release_candidate_blocked_observed")
        self.assertFalse(event["mutation_performed"])
        self.assertFalse(event["production_authority"])
        self.assertFalse(event["secret_values_recorded"])
        self.assertEqual(len(event["event_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
