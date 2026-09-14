from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE','PRODUCTION_RELEASE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','AUTH_SECURITY_POLICY_CHANGE','DATA_DELETION',
    'CUSTOMER_COMMITMENT','BID_SUBMISSION','PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT','FINANCIAL_COMMITMENT'
}
ALLOWED_ENVS = {'development','staging'}

@dataclass(frozen=True)
class ProviderAdapter:
    provider_id: str
    adapter_version: str
    capabilities: frozenset[str]
    healthy: bool
    credential_mode: str
    identity_attested: bool
    retention: str
    training: str


def validate_adapter(adapter: ProviderAdapter) -> dict:
    if not adapter.provider_id or not adapter.adapter_version:
        return {'status':'HOLD','reason':'ADAPTER_IDENTITY_REQUIRED'}
    if not adapter.capabilities:
        return {'status':'HOLD','reason':'CAPABILITY_DISCOVERY_REQUIRED'}
    if adapter.credential_mode not in {'oidc','ephemeral-token','none'}:
        return {'status':'HOLD','reason':'UNAPPROVED_CREDENTIAL_MODE'}
    if not adapter.identity_attested:
        return {'status':'HOLD','reason':'IDENTITY_ATTESTATION_REQUIRED'}
    if adapter.retention != 'none' or adapter.training != 'disabled':
        return {'status':'HOLD','reason':'PRIVACY_POLICY_MISMATCH'}
    if not adapter.healthy:
        return {'status':'HOLD','reason':'PROVIDER_UNHEALTHY'}
    return {'status':'READY','reason':'PROVIDER_ADAPTER_VALID'}


def select_provider(adapters: Iterable[ProviderAdapter], capability: str) -> dict:
    ready=[]
    rejected=[]
    for a in adapters:
        decision=validate_adapter(a)
        if decision['status']=='READY' and capability in a.capabilities:
            ready.append(a)
        else:
            rejected.append({'provider_id':a.provider_id,'reason':decision['reason'] if decision['status']!='READY' else 'CAPABILITY_MISMATCH'})
    if not ready:
        return {'status':'HOLD','reason':'NO_ATTESTED_PROVIDER','rejected':rejected,'production_locked':True}
    ready.sort(key=lambda a:(a.provider_id,a.adapter_version))
    return {'status':'READY','selected':ready[0].provider_id,'fallbacks':[a.provider_id for a in ready[1:]],'rejected':rejected,'production_locked':True}


def evaluate_slo(success_rate: float, p95_latency_ms: int, max_p95_ms: int=5000, min_success: float=0.99) -> dict:
    if not 0 <= success_rate <= 1 or p95_latency_ms < 0:
        return {'status':'HOLD','reason':'INVALID_TELEMETRY'}
    if success_rate < min_success:
        return {'status':'HOLD','reason':'SUCCESS_SLO_BREACH'}
    if p95_latency_ms > max_p95_ms:
        return {'status':'HOLD','reason':'LATENCY_SLO_BREACH'}
    return {'status':'PASS','reason':'SLO_WITHIN_BOUND'}


def evidence_freshness(age_hours: float, max_age_hours: float=24.0) -> dict:
    if age_hours < 0:
        return {'status':'HOLD','reason':'INVALID_EVIDENCE_AGE'}
    if age_hours > max_age_hours:
        return {'status':'HOLD','reason':'STALE_EVIDENCE'}
    return {'status':'PASS','reason':'EVIDENCE_FRESH'}


def authorize_scheduler_action(action: str, environment: str, read_only: bool, reversible: bool) -> dict:
    if action in HUMAN_ONLY:
        return {'decision':'HUMAN_REVIEW','reason':'HUMAN_ONLY_ACTION'}
    if environment not in ALLOWED_ENVS:
        return {'decision':'HOLD','reason':'NONPRODUCTION_ENVIRONMENT_REQUIRED'}
    if not read_only:
        return {'decision':'HOLD','reason':'SCHEDULED_WRITE_FORBIDDEN'}
    if not reversible:
        return {'decision':'HOLD','reason':'REVERSIBILITY_REQUIRED'}
    return {'decision':'ALLOW','reason':'BOUNDED_READ_ONLY_SCHEDULED_ACTION'}


def recovery_readiness(backup_evidence: bool, rollback_evidence: bool, restore_drill_evidence: bool, rto_minutes: int, max_rto_minutes: int=60) -> dict:
    if not backup_evidence:
        return {'status':'HOLD','reason':'BACKUP_EVIDENCE_REQUIRED'}
    if not rollback_evidence:
        return {'status':'HOLD','reason':'ROLLBACK_EVIDENCE_REQUIRED'}
    if not restore_drill_evidence:
        return {'status':'HOLD','reason':'RESTORE_DRILL_EVIDENCE_REQUIRED'}
    if rto_minutes < 0 or rto_minutes > max_rto_minutes:
        return {'status':'HOLD','reason':'RTO_TARGET_NOT_MET'}
    return {'status':'READY','reason':'RECOVERY_EVIDENCE_COMPLETE'}


def capacity_guard(requested_units: int, available_units: int, budget_units: int, environment: str) -> dict:
    if environment not in ALLOWED_ENVS:
        return {'decision':'HOLD','reason':'PRODUCTION_CAPACITY_FORBIDDEN'}
    if min(requested_units, available_units, budget_units) < 0:
        return {'decision':'HOLD','reason':'INVALID_CAPACITY'}
    if requested_units > available_units:
        return {'decision':'HOLD','reason':'CAPACITY_EXCEEDED'}
    if requested_units > budget_units:
        return {'decision':'HOLD','reason':'RESOURCE_BUDGET_EXCEEDED'}
    return {'decision':'ALLOW','reason':'BOUNDED_CAPACITY_ALLOWED'}
