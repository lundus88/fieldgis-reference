from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

ACTION_PRIORITY = {
    'HOLD': 100,
    'HUMAN_REVIEW': 90,
    'AUTO_PREPARE': 70,
    'MONITOR': 20,
}

ALLOWED_ACTIONS = frozenset(ACTION_PRIORITY)


@dataclass(frozen=True)
class DirectorSignal:
    workload_id: str
    action_class: str
    reason: str
    evidence_sha: str | None
    source_reference: str | None
    evidence_fresh: bool
    technical_score: float | None = None


def classify_signal(signal: DirectorSignal) -> dict:
    if not signal.workload_id:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'WORKLOAD_ID_REQUIRED'}
    if signal.action_class not in ALLOWED_ACTIONS:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'UNKNOWN_ACTION_CLASS'}
    if not signal.evidence_fresh:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'EVIDENCE_NOT_FRESH'}
    if not signal.evidence_sha or not signal.source_reference:
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'EVIDENCE_PROVENANCE_REQUIRED'}
    if signal.technical_score is not None and (signal.technical_score < 0 or signal.technical_score > 100):
        return {'action_class': 'HOLD', 'priority': 100, 'reason': 'INVALID_TECHNICAL_SCORE'}
    return {
        'action_class': signal.action_class,
        'priority': ACTION_PRIORITY[signal.action_class],
        'reason': signal.reason or 'NO_REASON_PROVIDED',
    }


def build_exception_queue(signals: Iterable[DirectorSignal]) -> list[dict]:
    queue = []
    for signal in signals:
        decision = classify_signal(signal)
        item = {
            'workload_id': signal.workload_id,
            'action_class': decision['action_class'],
            'priority': decision['priority'],
            'reason': decision['reason'],
            'evidence_sha': signal.evidence_sha,
            'source_reference': signal.source_reference,
            'evidence_fresh': signal.evidence_fresh,
            'technical_score': signal.technical_score,
        }
        queue.append(item)
    queue.sort(key=lambda item: (-item['priority'], item['workload_id']))
    return queue


def next_best_action(item: dict) -> str:
    action = item['action_class']
    if action == 'HOLD':
        return 'Refresh or repair trustworthy evidence before any consequential action.'
    if action == 'HUMAN_REVIEW':
        return 'Prepare a decision package for explicit human approval; do not execute.'
    if action == 'AUTO_PREPARE':
        return 'Prepare a bounded reversible non-production improvement candidate and validation evidence.'
    return 'Continue read-only monitoring and evidence refresh.'


def build_director_brief(signals: Iterable[DirectorSignal]) -> dict:
    queue = build_exception_queue(signals)
    counts = {key: 0 for key in ('HOLD', 'HUMAN_REVIEW', 'AUTO_PREPARE', 'MONITOR')}
    for item in queue:
        counts[item['action_class']] += 1
        item['next_best_action'] = next_best_action(item)

    overall = 'MONITOR'
    for candidate in ('HOLD', 'HUMAN_REVIEW', 'AUTO_PREPARE'):
        if counts[candidate]:
            overall = candidate
            break

    top_exception = queue[0] if queue else None
    return {
        'mode': 'READ_ONLY_NON_PRODUCTION',
        'overall_action_class': overall,
        'counts': counts,
        'top_exception': top_exception,
        'exceptions': queue,
        'autonomous_ceiling': 'PREPARE_PR',
        'production_authority': 'HUMAN_ONLY',
        'external_messaging': 'DISABLED',
    }
