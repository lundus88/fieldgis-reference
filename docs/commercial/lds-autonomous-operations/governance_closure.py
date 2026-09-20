#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class PolicyDecision:
    policy_version: str
    action_id: str
    known_action: bool
    environment: str
    risk_class: str
    evidence_current: bool
    human_only: bool=False

def evaluate_policy(p:PolicyDecision)->Dict:
    if not p.policy_version or not p.known_action:
        return {"status":"HUMAN_GATE","reason":"UNKNOWN_OR_UNVERSIONED_POLICY"}
    if not p.evidence_current:
        return {"status":"HUMAN_GATE","reason":"STALE_POLICY_EVIDENCE"}
    if p.human_only:
        return {"status":"HUMAN_GATE","reason":"HUMAN_ONLY_ACTION"}
    if p.environment=="PRODUCTION" and p.risk_class in {"HIGH","IRREVERSIBLE"}:
        return {"status":"HUMAN_GATE","reason":"PRODUCTION_CONSEQUENTIAL_ACTION"}
    return {"status":"PASS","reason":"POLICY_ALLOWS_BOUNDED_ACTION"}

@dataclass(frozen=True)
class AccessLeaseRequest:
    capability: str
    task_id: str
    least_privilege: bool
    ttl_minutes: int
    max_ttl_minutes: int
    secret_embedded: bool=False
    privilege_widening: bool=False
    production_admin: bool=False

def broker_access(a:AccessLeaseRequest)->Dict:
    if a.secret_embedded:
        return {"status":"HUMAN_GATE","reason":"SECRET_EMBEDDING_FORBIDDEN","lease_issued":False}
    if not a.least_privilege or a.privilege_widening:
        return {"status":"HUMAN_GATE","reason":"LEAST_PRIVILEGE_VIOLATION","lease_issued":False}
    if not a.task_id or not a.capability or a.ttl_minutes<=0 or a.ttl_minutes>a.max_ttl_minutes:
        return {"status":"HUMAN_GATE","reason":"INVALID_ACCESS_LEASE","lease_issued":False}
    if a.production_admin:
        return {"status":"HUMAN_GATE","reason":"PRODUCTION_ADMIN_REQUIRES_HUMAN","lease_issued":False}
    return {
        "status":"PASS","reason":"JIT_TASK_SCOPED_ACCESS_ALLOWED","lease_issued":True,
        "ttl_minutes":a.ttl_minutes,"revocation_required":True
    }

@dataclass(frozen=True)
class ProvenanceEvidence:
    source_ref_present: bool
    dependency_manifest_present: bool
    dependency_scan_pass: bool
    build_identity_present: bool
    artifact_digest_present: bool
    artifact_signature_or_attestation_present: bool
    regression_pass: bool

def provenance_gate(p:ProvenanceEvidence)->Dict:
    checks={
        "source_ref":p.source_ref_present,
        "dependency_manifest":p.dependency_manifest_present,
        "dependency_scan":p.dependency_scan_pass,
        "build_identity":p.build_identity_present,
        "artifact_digest":p.artifact_digest_present,
        "attestation":p.artifact_signature_or_attestation_present,
        "regression":p.regression_pass,
    }
    missing=sorted(k for k,v in checks.items() if not v)
    if missing:
        return {"status":"HUMAN_GATE","reason":"SUPPLY_CHAIN_PROVENANCE_INCOMPLETE","missing":missing,"release_claim_allowed":False}
    return {"status":"PASS","reason":"PROVENANCE_EVIDENCE_COMPLETE","release_claim_allowed":True,"production_authority":False}

@dataclass(frozen=True)
class ChaosScenario:
    environment: str
    credential_access: bool
    network_access: bool
    production_mutation: bool
    scenario_class: str
    expected_fail_closed: bool
    observed_fail_closed: bool

def chaos_verify(c:ChaosScenario)->Dict:
    if c.environment=="PRODUCTION" or c.production_mutation or c.credential_access:
        return {"status":"HUMAN_GATE","reason":"CHAOS_ISOLATION_VIOLATION"}
    if c.expected_fail_closed and not c.observed_fail_closed:
        return {"status":"HOLD","reason":"RESILIENCE_CONTROL_GAP"}
    return {"status":"PASS","reason":"NON_PRODUCTION_RESILIENCE_SCENARIO_PASS","scenario":c.scenario_class}

@dataclass(frozen=True)
class PortabilityEvidence:
    handover_package_ready: bool
    ownership_defined: bool
    export_evidence: bool
    credential_transfer_plan: bool
    access_revocation_plan: bool
    customer_acceptance: bool

def portability_gate(p:PortabilityEvidence)->Dict:
    checks={
        "handover_package":p.handover_package_ready,
        "ownership":p.ownership_defined,
        "export":p.export_evidence,
        "credential_transfer":p.credential_transfer_plan,
        "revocation":p.access_revocation_plan,
        "customer_acceptance":p.customer_acceptance,
    }
    missing=sorted(k for k,v in checks.items() if not v)
    if missing:
        return {"status":"HOLD","reason":"PORTABILITY_EXIT_EVIDENCE_INCOMPLETE","missing":missing}
    return {"status":"PASS","reason":"PORTABILITY_EXIT_READY","source_of_truth":"lds-handover-exit-package"}

@dataclass(frozen=True)
class BusinessHealth:
    evidence_current: bool
    margin_state: str
    capacity_state: str
    customer_health_state: str
    support_burden_state: str
    concentration_risk: str
    cost_anomaly: bool=False

def business_health_governor(b:BusinessHealth)->Dict:
    if not b.evidence_current:
        return {"status":"HUMAN_GATE","reason":"STALE_BUSINESS_HEALTH_EVIDENCE","admission":"HOLD"}
    severe=(
        b.margin_state=="CRITICAL" or
        b.capacity_state=="OVERLOADED" or
        b.customer_health_state=="CRITICAL" or
        b.support_burden_state=="CRITICAL" or
        b.concentration_risk=="CRITICAL" or
        b.cost_anomaly
    )
    if severe:
        return {
            "status":"AUTO_NOTIFY","reason":"BUSINESS_HEALTH_GUARD_ACTIVE",
            "admission":"CONSTRAIN_NEW_WORK","priority":"PROTECT_ACTIVE_COMMITMENTS",
            "pricing_mutation_allowed":False,"contract_mutation_allowed":False
        }
    return {"status":"PASS","reason":"BUSINESS_HEALTH_WITHIN_POLICY","admission":"NORMAL"}
