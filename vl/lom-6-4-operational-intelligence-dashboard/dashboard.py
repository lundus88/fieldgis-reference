from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

ACTION_PRIORITY = {
    'HOLD': 100,
    'HUMAN_REVIEW': 90,
    'AUTO_PREPARE': 70,
    'MONITOR': 20,
}

ALLOWED_HEALTH = frozenset(ACTION_PRIORITY)


@dataclass(frozen=True)
class WorkloadSnapshot:
    workload_id: str
    status: str
    health: str
    reason: str
    evidence_sha: str | None = None
    source_reference: str | None = None
    sample_count: int | None = None
    success_rate: float | None = None
    correctness: float | None = None
    safety: float | None = None
    p95_latency_ms: int | None = None
    evidence_fresh: bool = False


def _rate(value: float | None) -> float | None:
    if value is None or value < 0 or value > 1:
        return None
    return round(value, 6)


def classify_snapshot(snapshot: WorkloadSnapshot) -> dict:
    if not snapshot.workload_id:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'WORKLOAD_ID_REQUIRED'}
    if snapshot.status != 'READY':
        return {'action_class': 'HOLD', 'priority': 100, 'reason': snapshot.reason or 'MEASUREMENT_NOT_READY'}
    if not snapshot.evidence_fresh:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'EVIDENCE_NOT_FRESH'}
    if not snapshot.evidence_sha or not snapshot.source_reference:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'EVIDENCE_PROVENANCE_REQUIRED'}
    if snapshot.sample_count is None or snapshot.sample_count < 1:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'SAMPLE_COUNT_REQUIRED'}
    rates = (_rate(snapshot.success_rate), _rate(snapshot.correctness), _rate(snapshot.safety))
    if any(value is None for value in rates):
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'VALID_TECHNICAL_RATES_REQUIRED'}
    if snapshot.p95_latency_ms is None or snapshot.p95_latency_ms < 0:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'VALID_LATENCY_REQUIRED'}
    if snapshot.health not in ALLOWED_HEALTH:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'UNKNOWN_HEALTH_STATE'}

    action = snapshot.health
    return {'action_class': action, 'priority': ACTION_PRIORITY[action], 'reason': snapshot.reason}


def workload_card(snapshot: WorkloadSnapshot) -> dict:
    decision = classify_snapshot(snapshot)
    card = {
        'workload_id': snapshot.workload_id,
        'action_class': decision['action_class'],
        'priority': decision['priority'],
        'reason': decision['reason'],
        'evidence_fresh': snapshot.evidence_fresh,
        'evidence_sha': snapshot.evidence_sha,
        'source_reference': snapshot.source_reference,
        'sample_count': snapshot.sample_count,
        'success_rate': _rate(snapshot.success_rate),
        'correctness': _rate(snapshot.correctness),
        'safety': _rate(snapshot.safety),
        'p95_latency_ms': snapshot.p95_latency_ms,
    }
    card['technical_score'] = technical_score(card)
    return card


def technical_score(card: dict) -> float | None:
    if card.get('action_class') == 'HOLD':
        return None
    success = card.get('success_rate')
    correctness = card.get('correctness')
    safety = card.get('safety')
    latency = card.get('p95_latency_ms')
    if None in (success, correctness, safety, latency):
        return None
    latency_component = max(0.0, 1.0 - min(float(latency), 20000.0) / 20000.0)
    score = 100.0 * (0.30 * success + 0.30 * correctness + 0.30 * safety + 0.10 * latency_component)
    return round(score, 2)


def build_director_view(snapshots: Iterable[WorkloadSnapshot]) -> dict:
    cards = [workload_card(snapshot) for snapshot in snapshots]
    cards.sort(key=lambda card: (-card['priority'], card['workload_id']))
    counts = {key: 0 for key in ('HOLD', 'HUMAN_REVIEW', 'AUTO_PREPARE', 'MONITOR')}
    for card in cards:
        counts[card['action_class']] += 1

    overall = 'MONITOR'
    for action in ('HOLD', 'HUMAN_REVIEW', 'AUTO_PREPARE'):
        if counts[action]:
            overall = action
            break

    return {
        'mode': 'READ_ONLY_NON_PRODUCTION',
        'overall_action_class': overall,
        'counts': counts,
        'workloads': cards,
        'autonomous_ceiling': 'PREPARE_PR',
        'production_authority': 'HUMAN_ONLY',
    }
