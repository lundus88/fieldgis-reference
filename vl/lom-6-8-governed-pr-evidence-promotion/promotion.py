from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

SHA_RE = re.compile(r'^[0-9a-f]{40}$')
HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE','PRODUCTION_RELEASE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','AUTH_SECURITY_POLICY_CHANGE','DATA_DELETION',
    'CUSTOMER_COMMITMENT','BID_SUBMISSION','PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT','FINANCIAL_COMMITMENT',
}


@dataclass(frozen=True)
class PromotionRequest:
    workload_id: str
    base_sha: str
    candidate_sha: str
    evidence_sha: str
    source_reference: str
    validation_status: str
    rollback_plan_digest: str
    target_action: str
    production: bool = False
    risk: str = 'LOW'


def _valid_sha(value: str) -> bool:
    return bool(SHA_RE.fullmatch(value or ''))


def _manifest_payload(req: PromotionRequest) -> dict:
    return {
        'schema': 'lom.pr-evidence-promotion/1',
        'workload_id': req.workload_id,
        'base_sha': req.base_sha,
        'candidate_sha': req.candidate_sha,
        'evidence_sha': req.evidence_sha,
        'source_reference': req.source_reference,
        'validation_status': req.validation_status,
        'rollback_plan_digest': req.rollback_plan_digest,
        'target_action': req.target_action,
        'production': req.production,
        'risk': req.risk,
        'autonomous_ceiling': 'PREPARE_PR',
        'production_authority': 'HUMAN_ONLY',
        'auto_merge': 'DISABLED',
        'production_execution': 'DISABLED',
    }


def manifest_digest(req: PromotionRequest) -> str:
    payload = json.dumps(_manifest_payload(req), sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def validate_promotion(req: PromotionRequest) -> dict:
    if not req.workload_id:
        return {'status': 'HOLD', 'reason': 'WORKLOAD_ID_REQUIRED'}
    if not all(_valid_sha(value) for value in (req.base_sha, req.candidate_sha, req.evidence_sha)):
        return {'status': 'HOLD', 'reason': 'EXACT_SHA_REQUIRED'}
    if req.base_sha == req.candidate_sha:
        return {'status': 'HOLD', 'reason': 'CANDIDATE_MUST_DIFFER_FROM_BASE'}
    if not req.source_reference:
        return {'status': 'HOLD', 'reason': 'SOURCE_REFERENCE_REQUIRED'}
    if req.validation_status != 'PREPARE_PR':
        return {'status': 'HOLD', 'reason': 'SANDBOX_VALIDATION_REQUIRED'}
    if not req.rollback_plan_digest or len(req.rollback_plan_digest) < 16:
        return {'status': 'HOLD', 'reason': 'ROLLBACK_EVIDENCE_REQUIRED'}
    if req.risk not in {'LOW', 'MEDIUM', 'HIGH'}:
        return {'status': 'HOLD', 'reason': 'UNKNOWN_RISK'}
    if req.target_action in HUMAN_ONLY or req.production or req.risk == 'HIGH':
        return {'status': 'HUMAN_REVIEW', 'reason': 'HUMAN_BOUNDARY'}
    return {'status': 'PREPARE_PR', 'reason': 'EVIDENCE_PROMOTION_READY'}


def build_promotion_package(req: PromotionRequest) -> dict:
    decision = validate_promotion(req)
    manifest = _manifest_payload(req)
    manifest['manifest_sha256'] = manifest_digest(req)
    return {
        'status': decision['status'],
        'reason': decision['reason'],
        'manifest': manifest,
        'pr_candidate': {
            'base_sha': req.base_sha,
            'head_sha': req.candidate_sha,
            'human_merge_required': True,
        },
        'immutable_evidence_binding': True,
        'autonomous_ceiling': 'PREPARE_PR',
        'auto_merge': 'DISABLED',
        'production_execution': 'DISABLED',
        'external_action_execution': 'DISABLED',
    }
