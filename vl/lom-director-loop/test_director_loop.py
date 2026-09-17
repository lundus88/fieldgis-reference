import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parent / 'director_loop.py'
spec = importlib.util.spec_from_file_location('director_loop', MODULE)
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)


def observation(project_id, *, accessible=True, main_sha='abc123', signals=None):
    return {
        'project_id': project_id,
        'repository': f'lundus88/{project_id}',
        'accessible': accessible,
        'default_branch': 'main',
        'main_sha': main_sha,
        'signals': signals or ['MAIN_ACTIVE'],
        'evidence_refs': [f'commit:{main_sha}'] if main_sha else [f'status:{project_id}:no-main'],
    }


def payload(captured_at, observations):
    return {
        'schema': 'lom.portfolio-observation/2',
        'captured_at': captured_at,
        'mode': 'READ_ONLY_FAIL_CLOSED',
        'production_authority': 'HUMAN_ONLY',
        'observations': observations,
    }


class DirectorLoopTests(unittest.TestCase):
    def test_fresh_run_produces_ranked_priorities_and_human_authority(self):
        current = payload(
            '2026-09-17T00:50:00Z',
            [
                observation('review-project', signals=['MAIN_ACTIVE', 'OPEN_WORK_PR_1']),
                observation('healthy-project'),
            ],
        )
        now = datetime(2026, 9, 17, 1, 0, tzinfo=timezone.utc)
        brief = dl.build(now=now, payload=current)
        self.assertEqual(brief['freshness_status'], 'FRESH')
        self.assertEqual(brief['production_authority'], 'HUMAN_ONLY')
        self.assertEqual(brief['protected_main_merge_authority'], 'HUMAN_ONLY')
        self.assertEqual(brief['financial_commitment_authority'], 'HUMAN_ONLY')
        scores = [p['priority_score'] for p in brief['ranked_priorities']]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertTrue(all(p['authority'] == 'RECOMMENDATION_ONLY' for p in brief['ranked_priorities']))

    def test_stale_run_fails_closed_to_hold(self):
        stale_payload = payload(
            '2026-09-13T03:30:00Z',
            [observation('a'), observation('b', signals=['MAIN_ACTIVE', 'OPEN_WORK_PR_2'])],
        )
        now = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
        brief = dl.build(now=now, payload=stale_payload)
        self.assertEqual(brief['freshness_status'], 'STALE')
        self.assertTrue(all(p['health'] == 'HOLD' for p in brief['ranked_priorities']))
        self.assertTrue(all(e['category'] == 'EVIDENCE_GAP' for e in brief['director_exceptions']))

    def test_blocked_and_hold_are_never_auto_promoted(self):
        controlled = payload(
            '2026-09-17T00:50:00Z',
            [
                observation('blocked-project', signals=['MAIN_ACTIVE', 'RUNTIME_BLOCKED']),
                observation('hold-project', accessible=False, main_sha=None, signals=['SOURCE_NOT_AVAILABLE']),
            ],
        )
        now = datetime(2026, 9, 17, 1, 0, tzinfo=timezone.utc)
        brief = dl.build(now=now, payload=controlled)
        by_id = {p['project_id']: p for p in brief['ranked_priorities']}
        self.assertEqual(by_id['blocked-project']['health'], 'BLOCKED')
        self.assertEqual(by_id['hold-project']['health'], 'HOLD')
        self.assertEqual(by_id['blocked-project']['authority'], 'RECOMMENDATION_ONLY')
        self.assertEqual(by_id['hold-project']['authority'], 'RECOMMENDATION_ONLY')


if __name__ == '__main__':
    unittest.main()
