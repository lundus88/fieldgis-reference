from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE', 'PRODUCTION_RELEASE', 'PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING', 'AUTH_SECURITY_POLICY_CHANGE', 'DATA_DELETION',
    'CUSTOMER_COMMITMENT', 'BID_SUBMISSION', 'PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT', 'FINANCIAL_COMMITMENT', 'PRODUCTION_APPROVAL'
}

ALLOWED_ENVIRONMENTS = {'development', 'staging'}


@dataclass(frozen=True)
class AgentRecord:
    agent_id: str
    version: str
    role: str
    capabilities: frozenset[str]
    owner: str
    status: str = 'active'


@dataclass(frozen=True)
class AgentMetrics:
    success_rate: float
    correctness: float
    safety: float
    p95_latency_ms: int
    cost_per_task: float
    business_value_per_task: float


def validate_agent(record: AgentRecord) -> dict:
    if not record.agent_id or not record.version or not record.role or not record.owner:
        return {'status': 'HOLD', 'reason': 'AGENT_IDENTITY_INCOMPLETE'}
    if not record.capabilities:
        return {'status': 'HOLD', 'reason': 'CAPABILITIES_REQUIRED'}
    if record.status not in {'active', 'paused', 'deprecated'}:
        return {'status': 'HOLD', 'reason': 'INVALID_AGENT_STATUS'}
    return {'status': 'READY', 'reason': 'AGENT_REGISTERED'}


def score_agent(metrics: AgentMetrics) -> dict:
    values = [metrics.success_rate, metrics.correctness, metrics.safety]
    if any(v < 0 or v > 1 for v in values) or metrics.p95_latency_ms < 0 or metrics.cost_per_task < 0 or metrics.business_value_per_task < 0:
        return {'status': 'HOLD', 'reason': 'INVALID_METRICS'}

    quality = 100 * (0.35 * metrics.correctness + 0.35 * metrics.success_rate + 0.30 * metrics.safety)
    latency_penalty = min(metrics.p95_latency_ms / 1000.0, 20.0)
    efficiency = 100.0 if metrics.cost_per_task == 0 else min(100.0, 100.0 * metrics.business_value_per_task / metrics.cost_per_task)
    overall = max(0.0, min(100.0, 0.65 * quality + 0.20 * efficiency + 0.15 * (100.0 - latency_penalty)))
    status = 'PASS' if overall >= 80 and metrics.safety >= 0.99 else 'REVIEW'
    return {
        'status': status,
        'quality_score': round(quality, 2),
        'efficiency_score': round(efficiency, 2),
        'overall_score': round(overall, 2),
    }


def roi_summary(tasks: int, ai_cost: float, human_cost_saved: float, revenue_generated: float, error_cost_avoided: float = 0.0) -> dict:
    if tasks < 0 or min(ai_cost, human_cost_saved, revenue_generated, error_cost_avoided) < 0:
        return {'status': 'HOLD', 'reason': 'INVALID_FINOPS_INPUT'}
    gross_value = human_cost_saved + revenue_generated + error_cost_avoided
    net_value = gross_value - ai_cost
    roi_pct = None if ai_cost == 0 else (net_value / ai_cost) * 100.0
    return {
        'status': 'PASS',
        'tasks': tasks,
        'ai_cost': round(ai_cost, 2),
        'gross_value': round(gross_value, 2),
        'net_value': round(net_value, 2),
        'roi_pct': None if roi_pct is None else round(roi_pct, 2),
        'value_per_task': 0.0 if tasks == 0 else round(gross_value / tasks, 2),
    }


def recommend_agent(records: Iterable[AgentRecord], metrics_by_agent: dict[str, AgentMetrics], required_capability: str) -> dict:
    candidates = []
    rejected = []
    for record in records:
        registration = validate_agent(record)
        if registration['status'] != 'READY' or record.status != 'active':
            rejected.append({'agent_id': record.agent_id, 'reason': registration['reason'] if registration['status'] != 'READY' else 'AGENT_NOT_ACTIVE'})
            continue
        if required_capability not in record.capabilities:
            rejected.append({'agent_id': record.agent_id, 'reason': 'CAPABILITY_MISMATCH'})
            continue
        metrics = metrics_by_agent.get(record.agent_id)
        if metrics is None:
            rejected.append({'agent_id': record.agent_id, 'reason': 'METRICS_REQUIRED'})
            continue
        score = score_agent(metrics)
        if score['status'] == 'HOLD':
            rejected.append({'agent_id': record.agent_id, 'reason': score['reason']})
            continue
        candidates.append((score['overall_score'], record.agent_id, score))

    if not candidates:
        return {'status': 'HOLD', 'reason': 'NO_QUALIFIED_AGENT', 'rejected': rejected}
    candidates.sort(key=lambda item: (-item[0], item[1]))
    best = candidates[0]
    return {
        'status': 'READY',
        'selected_agent': best[1],
        'score': best[2],
        'fallbacks': [item[1] for item in candidates[1:]],
        'rejected': rejected,
    }


def agent_health(record: AgentRecord, metrics: AgentMetrics | None, evidence_fresh: bool) -> dict:
    registration = validate_agent(record)
    if registration['status'] != 'READY':
        return {'health': 'HOLD', 'reason': registration['reason']}
    if not evidence_fresh:
        return {'health': 'HOLD', 'reason': 'STALE_OR_MISSING_EVIDENCE'}
    if metrics is None:
        return {'health': 'HOLD', 'reason': 'METRICS_REQUIRED'}
    score = score_agent(metrics)
    if score['status'] == 'HOLD':
        return {'health': 'HOLD', 'reason': score['reason']}
    if record.status != 'active':
        return {'health': 'MONITOR', 'reason': 'AGENT_NOT_ACTIVE', 'score': score['overall_score']}
    if metrics.safety < 0.99:
        return {'health': 'HUMAN_REVIEW', 'reason': 'SAFETY_THRESHOLD_BREACH', 'score': score['overall_score']}
    if score['overall_score'] < 80:
        return {'health': 'AUTO_PREPARE', 'reason': 'PERFORMANCE_IMPROVEMENT_REQUIRED', 'score': score['overall_score']}
    return {'health': 'MONITOR', 'reason': 'HEALTHY', 'score': score['overall_score']}


def authorize_control_plane_action(action: str, environment: str, authority_change: bool = False) -> dict:
    if action in HUMAN_ONLY or authority_change:
        return {'decision': 'HUMAN_REVIEW', 'reason': 'HUMAN_ONLY_BOUNDARY'}
    if environment not in ALLOWED_ENVIRONMENTS:
        return {'decision': 'HOLD', 'reason': 'NONPRODUCTION_ENVIRONMENT_REQUIRED'}
    return {'decision': 'ALLOW', 'reason': 'BOUNDED_NONPRODUCTION_ACTION'}
