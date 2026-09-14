from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE', 'PRODUCTION_RELEASE', 'PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING', 'AUTH_SECURITY_POLICY_CHANGE', 'DATA_DELETION',
    'CUSTOMER_COMMITMENT', 'BID_SUBMISSION', 'PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT', 'FINANCIAL_COMMITMENT',
}

ALLOWED_ACTION_CLASSES = {'HOLD', 'HUMAN_REVIEW', 'AUTO_PREPARE', 'MONITOR'}
ALLOWED_RISK = {'LOW', 'MEDIUM', 'HIGH'}


@dataclass(frozen=True)
class RemediationSignal:
    workload_id: str
    action_class: str
    reason: str
    evidence_sha: str | None
    source_reference: str | None
    evidence_fresh: bool
    target_action: str
    risk: str
    reversible: bool
    production: bool = False


def classify(signal: RemediationSignal) -> dict:
    if not signal.workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_ID_REQUIRED'}
    if signal.action_class not in ALLOWED_ACTION_CLASSES:
        return {'status': 'HOLD', 'reason': 'UNKNOWN_ACTION_CLASS'}
    if not signal.evidence_fresh:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_NOT_FRESH'}
    if not signal.evidence_sha or not signal.source_reference:
        return {'status': 'HOLD', 'reason': 'EVIDENCE_PROVENANCE_REQUIRED'}
    if signal.risk not in ALLOWED_RISK:
        return {'status': 'HOLD', 'reason': 'UNKNOWN_RISK'}
    if signal.target_action in HUMAN_ONLY or signal.production or signal.risk == 'HIGH':
        return {'status': 'HUMAN_REVIEW', 'reason': 'HUMAN_BOUNDARY'}
    if not signal.reversible:
        return {'status': 'HOLD', 'reason': 'REVERSIBILITY_REQUIRED'}
    if signal.action_class == 'HOLD':
        return {'status': 'HOLD', 'reason': signal.reason or 'UPSTREAM_HOLD'}
    if signal.action_class == 'HUMAN_REVIEW':
        return {'status': 'HUMAN_REVIEW', 'reason': signal.reason or 'UPSTREAM_HUMAN_REVIEW'}
    if signal.action_class == 'AUTO_PREPARE':
        return {'status': 'PREPARE_PR', 'reason': 'BOUNDED_REMEDIATION_ALLOWED'}
    return {'status': 'MONITOR', 'reason': 'NO_REMEDIATION_REQUIRED'}


def build_plan(signal: RemediationSignal) -> dict:
    decision = classify(signal)
    plan = {
        'workload_id': signal.workload_id,
        'status': decision['status'],
        'reason': decision['reason'],
        'evidence_sha': signal.evidence_sha,
        'source_reference': signal.source_reference,
        'target_action': signal.target_action,
        'risk': signal.risk,
        'reversible': signal.reversible,
        'production': signal.production,
        'mode': 'NON_PRODUCTION',
        'autonomous_ceiling': 'PREPARE_PR',
        'production_authority': 'HUMAN_ONLY',
        'external_action_execution': 'DISABLED',
    }
    if decision['status'] == 'PREPARE_PR':
        plan['steps'] = [
            'Define bounded reversible change.',
            'Run sandbox or non-production validation.',
            'Run regression and safety checks.',
            'Attach exact evidence and rollback plan.',
            'Prepare PR candidate for human review.',
        ]
    elif decision['status'] == 'HUMAN_REVIEW':
        plan['steps'] = ['Prepare decision package for explicit human approval; do not execute.']
    elif decision['status'] == 'HOLD':
        plan['steps'] = ['Resolve evidence, reversibility, or authority blocker before planning execution.']
    else:
        plan['steps'] = ['Continue monitoring; no remediation package required.']
    return plan


def build_remediation_queue(signals: Iterable[RemediationSignal]) -> list[dict]:
    priority = {'HOLD': 100, 'HUMAN_REVIEW': 90, 'PREPARE_PR': 70, 'MONITOR': 20}
    plans = [build_plan(signal) for signal in signals]
    plans.sort(key=lambda p: (-priority[p['status']], p['workload_id']))
    return plans
