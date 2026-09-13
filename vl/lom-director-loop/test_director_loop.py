import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE = Path(__file__).parent / 'director_loop.py'
spec = importlib.util.spec_from_file_location('director_loop', MODULE)
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)


def test_fresh_run_produces_ranked_priorities_and_human_authority():
    now = datetime(2026, 9, 13, 3, 40, tzinfo=timezone.utc)
    brief = dl.build(now=now)
    assert brief['freshness_status'] == 'FRESH'
    assert brief['production_authority'] == 'HUMAN_ONLY'
    assert brief['protected_main_merge_authority'] == 'HUMAN_ONLY'
    assert brief['financial_commitment_authority'] == 'HUMAN_ONLY'
    scores = [p['priority_score'] for p in brief['ranked_priorities']]
    assert scores == sorted(scores, reverse=True)
    assert all(p['authority'] == 'RECOMMENDATION_ONLY' for p in brief['ranked_priorities'])


def test_stale_run_fails_closed_to_hold():
    now = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    brief = dl.build(now=now)
    assert brief['freshness_status'] == 'STALE'
    assert all(p['health'] == 'HOLD' for p in brief['ranked_priorities'])
    assert all(e['category'] == 'EVIDENCE_GAP' for e in brief['director_exceptions'])


def test_blocked_and_hold_are_never_auto_promoted():
    now = datetime(2026, 9, 13, 3, 40, tzinfo=timezone.utc)
    brief = dl.build(now=now)
    by_id = {p['project_id']: p for p in brief['ranked_priorities']}
    assert by_id['lunduslead']['health'] == 'BLOCKED'
    assert by_id['kontenstudio']['health'] == 'HOLD'
    assert by_id['lunduslead']['authority'] == 'RECOMMENDATION_ONLY'
    assert by_id['kontenstudio']['authority'] == 'RECOMMENDATION_ONLY'
