import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parent / 'scheduler_guard.py'
spec = importlib.util.spec_from_file_location('scheduler_guard', MODULE)
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)


class SchedulerGuardTests(unittest.TestCase):
    def test_normal_primary_runs_with_ok_status(self):
        decision = sg.evaluate_schedule(
            event_name='schedule',
            schedule_expr=sg.PRIMARY_CRON,
            now=datetime(2026, 9, 18, 0, 45, tzinfo=timezone.utc),
            prior_evidence_runs=[],
        )
        self.assertEqual(decision['action'], 'RUN')
        self.assertEqual(decision['scheduler_status'], 'SCHEDULER_OK')
        self.assertEqual(decision['observed_condition'], 'PRIMARY_TRIGGER')
        self.assertEqual(decision['delay_minutes'], 8)

    def test_delayed_primary_still_runs_and_is_explicitly_marked(self):
        decision = sg.evaluate_schedule(
            event_name='schedule',
            schedule_expr=sg.PRIMARY_CRON,
            now=datetime(2026, 9, 18, 4, 56, tzinfo=timezone.utc),
            prior_evidence_runs=[],
        )
        self.assertEqual(decision['action'], 'RUN')
        self.assertEqual(decision['scheduler_status'], 'DELAYED')
        self.assertGreater(decision['delay_minutes'], sg.PRIMARY_GRACE_MINUTES)

    def test_missed_primary_is_recovered_by_catchup(self):
        decision = sg.evaluate_schedule(
            event_name='schedule',
            schedule_expr=sg.CATCHUP_CRON,
            now=datetime(2026, 9, 18, 6, 50, tzinfo=timezone.utc),
            prior_evidence_runs=[],
        )
        self.assertEqual(decision['action'], 'RUN')
        self.assertEqual(decision['scheduler_status'], 'RECOVERED')
        self.assertEqual(decision['observed_condition'], 'MISSED_PRIMARY')

    def test_catchup_noops_when_daily_brief_artifact_already_exists(self):
        decision = sg.evaluate_schedule(
            event_name='schedule',
            schedule_expr=sg.CATCHUP_CRON,
            now=datetime(2026, 9, 18, 6, 50, tzinfo=timezone.utc),
            prior_evidence_runs=[
                {
                    'run_id': '123',
                    'created_at': '2026-09-18T04:56:00Z',
                    'artifact': 'lom-director-brief-123',
                }
            ],
        )
        self.assertEqual(decision['action'], 'SKIP')
        self.assertEqual(decision['scheduler_status'], 'SCHEDULER_OK')
        self.assertEqual(decision['observed_condition'], 'DAILY_BRIEF_ALREADY_PRODUCED')

    def test_guard_discovery_failure_uses_safe_read_only_recovery_run(self):
        decision = sg.evaluate_schedule(
            event_name='schedule',
            schedule_expr=sg.PRIMARY_CRON,
            now=datetime(2026, 9, 18, 0, 45, tzinfo=timezone.utc),
            prior_evidence_runs=[],
            discovery_error='RuntimeError:API_UNAVAILABLE',
        )
        self.assertEqual(decision['action'], 'RUN')
        self.assertEqual(decision['scheduler_status'], 'SCHEDULER_DEGRADED')
        self.assertEqual(decision['observed_condition'], 'GUARD_DISCOVERY_UNAVAILABLE')

    def test_unknown_schedule_fails_closed(self):
        decision = sg.evaluate_schedule(
            event_name='schedule',
            schedule_expr='1 2 3 4 5',
            now=datetime(2026, 9, 18, 2, 1, tzinfo=timezone.utc),
            prior_evidence_runs=[],
        )
        self.assertEqual(decision['action'], 'HOLD')
        self.assertEqual(decision['scheduler_status'], 'SCHEDULER_DEGRADED')
        self.assertEqual(decision['observed_condition'], 'UNKNOWN_SCHEDULE')


if __name__ == '__main__':
    unittest.main()
