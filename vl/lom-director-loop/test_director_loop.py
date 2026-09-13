import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parent / 'director_loop.py'
spec = importlib.util.spec_from_file_location('director_loop', MODULE)
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)


class DirectorLoopTests(unittest.TestCase):
    def test_fresh_run_produces_ranked_priorities_and_human_authority(self):
        now = datetime(2026, 9, 13, 3, 40, tzinfo=timezone.utc)
        brief = dl.build(now=now)
        self.assertEqual(brief['freshness_status'], 'FRESH')
        self.assertEqual(brief['production_authority'], 'HUMAN_ONLY')
        self.assertEqual(brief['protected_main_merge_authority'], 'HUMAN_ONLY')
        self.assertEqual(brief['financial_commitment_authority'], 'HUMAN_ONLY')
        scores = [p['priority_score'] for p in brief['ranked_priorities']]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(p['authority'] == 'RECOMMENDATION_ONLY' for p in brief['ranked_priorities']))

    def test_stale_run_fails_closed_to_hold(self):
        now = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
        brief = dl.build(now=now)
        self.assertEqual(brief['freshness_status'], 'STALE')
        self.assertTrue(all(p['health'] == 'HOLD' for p in brief['ranked_priorities']))
        self.assertTrue(all(e['category'] == 'EVIDENCE_GAP' for e in brief['director_exceptions']))

    def test_blocked_and_hold_are_never_auto_promoted(self):
        now = datetime(2026, 9, 13, 3, 40, tzinfo=timezone.utc)
        brief = dl.build(now=now)
        by_id = {p['project_id']: p for p in brief['ranked_priorities']}
        self.assertEqual(by_id['lunduslead']['health'], 'BLOCKED')
        self.assertEqual(by_id['kontenstudio']['health'], 'HOLD')
        self.assertEqual(by_id['lunduslead']['authority'], 'RECOMMENDATION_ONLY')
        self.assertEqual(by_id['kontenstudio']['authority'], 'RECOMMENDATION_ONLY')


if __name__ == '__main__':
    unittest.main()
