from __future__ import annotations

from dataclasses import dataclass

HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE','PRODUCTION_RELEASE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','AUTH_SECURITY_POLICY_CHANGE','DATA_DELETION',
    'CUSTOMER_COMMITMENT','BID_SUBMISSION','PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT','FINANCIAL_COMMITMENT',
}

@dataclass(frozen=True)
class ValidationRequest:
    workload_id: str
    evidence_sha: str | None
    source_reference: str | None
    evidence_fresh: bool
    target_action: str
    risk: str
    reversible: bool
    production: bool
    ephemeral: bool
    network_disabled: bool
    production_credentials_absent: bool
    rollback_plan_present: bool
    build_passed: bool
    regression_passed: bool
    security_passed: bool
    independent_validation_passed: bool


def validate(req: ValidationRequest) -> dict:
    if not req.workload_id:
        return {'status':'HOLD','reason':'WORKLOAD_ID_REQUIRED'}
    if not req.evidence_fresh or not req.evidence_sha or not req.source_reference:
        return {'status':'HOLD','reason':'EVIDENCE_NOT_READY'}
    if req.target_action in HUMAN_ONLY or req.production or req.risk == 'HIGH':
        return {'status':'HUMAN_REVIEW','reason':'HUMAN_BOUNDARY'}
    if req.risk not in {'LOW','MEDIUM','HIGH'}:
        return {'status':'HOLD','reason':'UNKNOWN_RISK'}
    if not req.reversible:
        return {'status':'HOLD','reason':'REVERSIBILITY_REQUIRED'}
    if not req.ephemeral:
        return {'status':'HOLD','reason':'EPHEMERAL_SANDBOX_REQUIRED'}
    if not req.network_disabled:
        return {'status':'HOLD','reason':'NETWORK_MUST_BE_DISABLED'}
    if not req.production_credentials_absent:
        return {'status':'HOLD','reason':'PRODUCTION_CREDENTIALS_FORBIDDEN'}
    if not req.rollback_plan_present:
        return {'status':'HOLD','reason':'ROLLBACK_PLAN_REQUIRED'}
    checks = {
        'build': req.build_passed,
        'regression': req.regression_passed,
        'security': req.security_passed,
        'independent_validation': req.independent_validation_passed,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        return {'status':'HOLD','reason':'VALIDATION_FAILED','failed_checks':failed}
    return {'status':'PREPARE_PR','reason':'SANDBOX_VALIDATED','failed_checks':[]}


def validation_package(req: ValidationRequest) -> dict:
    decision = validate(req)
    return {
        'workload_id': req.workload_id,
        'status': decision['status'],
        'reason': decision['reason'],
        'failed_checks': decision.get('failed_checks', []),
        'evidence_sha': req.evidence_sha,
        'source_reference': req.source_reference,
        'sandbox': {
            'ephemeral': req.ephemeral,
            'network_disabled': req.network_disabled,
            'production_credentials_absent': req.production_credentials_absent,
        },
        'rollback_plan_present': req.rollback_plan_present,
        'autonomous_ceiling':'PREPARE_PR',
        'production_authority':'HUMAN_ONLY',
        'auto_merge':'DISABLED',
        'production_execution':'DISABLED',
        'authority_widening':'DISABLED',
    }
