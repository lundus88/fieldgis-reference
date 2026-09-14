from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

SHA_RE = re.compile(r'^[0-9a-f]{40}$')
DIGEST_RE = re.compile(r'^[0-9a-f]{64}$')
HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE','PRODUCTION_RELEASE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','AUTH_SECURITY_POLICY_CHANGE','DATA_DELETION',
    'CUSTOMER_COMMITMENT','BID_SUBMISSION','PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT','FINANCIAL_COMMITMENT',
}


@dataclass(frozen=True)
class DecisionRequest:
    workload_id: str
    base_sha: str
    candidate_sha: str
    evidence_sha: str
    manifest_sha256: str
    promotion_manifest: dict
    source_reference: str
    promotion_status: str
    rollback_ready: bool
    residual_risks: tuple[str, ...]
    target_action: str
    risk: str
    production: bool = False


def _valid_sha(value: str) -> bool:
    return bool(SHA_RE.fullmatch(value or ''))


def _valid_digest(value: str) -> bool:
    return bool(DIGEST_RE.fullmatch(value or ''))


def _canonical_manifest_digest(manifest: dict) -> str:
    payload = dict(manifest or {})
    claimed = payload.pop('manifest_sha256', None)
    if claimed is not None and not _valid_digest(claimed):
        return ''
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def _manifest_matches_request(req: DecisionRequest) -> bool:
    m = req.promotion_manifest or {}
    return all([
        m.get('schema') == 'lom.pr-evidence-promotion/2',
        m.get('workload_id') == req.workload_id,
        m.get('base_sha') == req.base_sha,
        m.get('candidate_sha') == req.candidate_sha,
        m.get('evidence_sha') == req.evidence_sha,
        m.get('source_reference') == req.source_reference,
        m.get('target_action') == req.target_action,
        m.get('production') == req.production,
        m.get('risk') == req.risk,
        m.get('validation_status') == 'PREPARE_PR',
        _valid_digest(m.get('validation_package_sha256', '')),
        _valid_digest(m.get('rollback_plan_sha256', '')),
        m.get('autonomous_ceiling') == 'PREPARE_PR',
        m.get('production_authority') == 'HUMAN_ONLY',
        m.get('auto_merge') == 'DISABLED',
        m.get('production_execution') == 'DISABLED',
    ])


def classify(req: DecisionRequest) -> dict:
    if not req.workload_id:
        return {'status':'HOLD','reason':'WORKLOAD_ID_REQUIRED'}
    if not all(_valid_sha(v) for v in (req.base_sha, req.candidate_sha, req.evidence_sha)):
        return {'status':'HOLD','reason':'EXACT_SHA_REQUIRED'}
    if req.base_sha == req.candidate_sha:
        return {'status':'HOLD','reason':'CANDIDATE_MUST_DIFFER_FROM_BASE'}
    if not _valid_digest(req.manifest_sha256):
        return {'status':'HOLD','reason':'MANIFEST_DIGEST_REQUIRED'}
    if not req.source_reference:
        return {'status':'HOLD','reason':'SOURCE_REFERENCE_REQUIRED'}
    if req.promotion_status != 'PREPARE_PR':
        return {'status':'HOLD','reason':'PROMOTION_NOT_READY'}
    if not _manifest_matches_request(req):
        return {'status':'HOLD','reason':'PROMOTION_MANIFEST_IDENTITY_MISMATCH'}
    computed = _canonical_manifest_digest(req.promotion_manifest)
    if not computed or computed != req.manifest_sha256:
        return {'status':'HOLD','reason':'PROMOTION_MANIFEST_DIGEST_MISMATCH'}
    claimed = req.promotion_manifest.get('manifest_sha256')
    if claimed is not None and claimed != req.manifest_sha256:
        return {'status':'HOLD','reason':'PROMOTION_MANIFEST_DIGEST_MISMATCH'}
    if not req.rollback_ready:
        return {'status':'HOLD','reason':'ROLLBACK_NOT_READY'}
    if req.risk not in {'LOW','MEDIUM','HIGH'}:
        return {'status':'HOLD','reason':'UNKNOWN_RISK'}
    if req.target_action in HUMAN_ONLY or req.production or req.risk == 'HIGH':
        return {'status':'HUMAN_REVIEW','reason':'HUMAN_BOUNDARY'}
    return {'status':'READY_FOR_HUMAN_DECISION','reason':'DECISION_PACKAGE_COMPLETE'}


def recommended_disposition(req: DecisionRequest) -> str:
    decision = classify(req)
    if decision['status'] == 'HOLD':
        return 'HOLD'
    if decision['status'] == 'HUMAN_REVIEW':
        return 'REVIEW_REQUIRED'
    if req.residual_risks:
        return 'APPROVE_ONLY_IF_RESIDUAL_RISKS_ACCEPTED'
    return 'APPROVE_OR_REJECT_EXPLICITLY'


def build_decision_package(req: DecisionRequest) -> dict:
    decision = classify(req)
    return {
        'schema':'lom.human-approval-decision-package/2',
        'workload_id':req.workload_id,
        'status':decision['status'],
        'reason':decision['reason'],
        'identity':{
            'base_sha':req.base_sha,
            'candidate_sha':req.candidate_sha,
            'evidence_sha':req.evidence_sha,
            'manifest_sha256':req.manifest_sha256,
            'source_reference':req.source_reference,
        },
        'evidence_chain':{
            'promotion_manifest_verified': decision['status'] != 'HOLD',
            'validation_package_sha256': (req.promotion_manifest or {}).get('validation_package_sha256'),
            'rollback_plan_sha256': (req.promotion_manifest or {}).get('rollback_plan_sha256'),
            'promotion_manifest_sha256': req.manifest_sha256,
        },
        'release_readiness':{
            'promotion_status':req.promotion_status,
            'rollback_ready':req.rollback_ready,
            'risk':req.risk,
            'production':req.production,
            'residual_risks':list(req.residual_risks),
        },
        'recommended_disposition':recommended_disposition(req),
        'human_decision_required':True,
        'allowed_human_decisions':['APPROVE','REJECT','REQUEST_CHANGES'],
        'autonomous_ceiling':'PREPARE_PR',
        'auto_approve':'DISABLED',
        'auto_merge':'DISABLED',
        'production_deploy':'DISABLED',
        'external_action_execution':'DISABLED',
    }
