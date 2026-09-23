from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

REQUIRED_EXTERNAL_GATES = (
    "DEDICATED_BUSINESS_PHONE",
    "COMPANY_ACCOUNT",
)

REQUIRED_RUNTIME_SECTIONS = (
    "business_licence",
    "legal_trust",
    "domain_email",
    "lead_intake",
    "payment",
)

KILL_SWITCHES = {
    "lead_intake": {
        "control":"LEAD_INTAKE_DISABLE",
        "scope":"PUBLIC_LEAD_INTAKE_ONLY",
        "preserves":["informational_site","support_contact"],
    },
    "checkout": {
        "control":"CHECKOUT_DISABLE",
        "scope":"NEW_CHECKOUT_ONLY",
        "preserves":["informational_site","existing_order_evidence"],
    },
    "billing": {
        "control":"BILLING_DISABLE",
        "scope":"NEW_CHARGING_ONLY",
        "preserves":["informational_site","support_contact","existing_order_evidence"],
    },
    "notification": {
        "control":"NOTIFICATION_PAUSE",
        "scope":"OUTBOUND_NOTIFICATION_ONLY",
        "preserves":["authoritative_order_state","payment_state","support_path"],
    },
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def evaluate_cutover_preflight(
    snapshot: dict[str,Any],
    *,
    external_gates: dict[str,str],
) -> dict[str,Any]:
    missing=[]
    for gate in REQUIRED_EXTERNAL_GATES:
        actual=external_gates.get(gate)
        if actual!="PASS":
            missing.append({"gate":gate,"required":"PASS","actual":actual or "MISSING"})

    for section in REQUIRED_RUNTIME_SECTIONS:
        actual=(snapshot.get(section) or {}).get("status")
        if actual!="PASS":
            missing.append({"gate":section.upper(),"required":"PASS","actual":actual or "MISSING"})

    if (snapshot.get("lead_intake") or {}).get("production_activation_authorized") is not True:
        missing.append({
            "gate":"LIVE_LEAD_INTAKE_AUTHORITY",
            "required":"CONTROLLED_AUTHORITY",
            "actual":"NOT_AUTHORIZED",
        })
    if (snapshot.get("payment") or {}).get("production_activation_authorized") is not True:
        missing.append({
            "gate":"PAYMENT_PRODUCTION_AUTHORITY",
            "required":"CONTROLLED_AUTHORITY",
            "actual":"NOT_AUTHORIZED",
        })

    return {
        "schema":"ld.cutover-preflight/1",
        "decision":"PASS" if not missing else "HOLD",
        "missing":missing,
        "production_mutation_performed":False,
        "live_payment_performed":False,
        "public_launch_authorized":False,
    }

def kill_switch_matrix() -> dict[str,Any]:
    return {
        "schema":"ld.kill-switch-matrix/1",
        "controls":json.loads(json.dumps(KILL_SWITCHES)),
        "independent_controls":True,
        "rule":"Disabling checkout or billing must not require taking down the informational site.",
        "production_mutation_performed":False,
    }

def validate_rollback_contract(contract:dict[str,Any]) -> dict[str,Any]:
    required=[
        "candidate_deployment_ref",
        "known_good_deployment_ref",
        "lead_intake_disable_ref",
        "checkout_disable_ref",
        "billing_disable_ref",
        "incident_path_ref",
        "rollback_procedure_ref",
    ]
    missing=[k for k in required if not contract.get(k)]
    if missing:
        return {"decision":"HOLD","reason":"ROLLBACK_CONTRACT_INCOMPLETE","missing":missing}
    if contract["candidate_deployment_ref"]==contract["known_good_deployment_ref"]:
        return {"decision":"HOLD","reason":"KNOWN_GOOD_MUST_DIFFER_FROM_CANDIDATE"}
    return {
        "decision":"READINESS_PASS",
        "schema":"ld.rollback-contract/1",
        "live_rollback_performed":False,
        "production_mutation_performed":False,
        "contract_digest":_digest(contract),
    }

def build_customer_zero_rehearsal(
    *,
    preflight:dict[str,Any],
    rollback_contract:dict[str,Any],
) -> dict[str,Any]:
    rollback=validate_rollback_contract(rollback_contract)
    return {
        "schema":"ld.customer-zero-rehearsal/1",
        "synthetic_only":True,
        "real_customer":False,
        "payment_transactions":0,
        "production_mutations":0,
        "public_launch_authorized":False,
        "preflight_decision":preflight.get("decision"),
        "rollback_decision":rollback.get("decision"),
        "expected_live_action":"STOP_AT_HUMAN_GATE",
        "decision":"READINESS_PASS" if rollback.get("decision")=="READINESS_PASS" else "HOLD",
    }

def build_future_live_evidence_manifest() -> dict[str,Any]:
    fields=[
        "dedicated_business_phone_evidence_ref",
        "company_account_evidence_ref",
        "commercial_origin_fingerprint",
        "lead_intake_security_fingerprint",
        "payment_provider_fingerprint",
        "signed_webhook_evidence_ref",
        "candidate_deployment_ref",
        "known_good_deployment_ref",
        "lead_intake_disable_test_ref",
        "checkout_disable_test_ref",
        "billing_disable_test_ref",
        "incident_path_ref",
        "rollback_drill_ref",
        "golden_transaction_evidence_ref",
        "reconciliation_evidence_ref",
    ]
    return {
        "schema":"ld.future-live-evidence-manifest/1",
        "status":"EMPTY_TEMPLATE",
        "evidence":{k:None for k in fields},
        "rule":"No field may be marked complete without attributable live evidence.",
        "production_authority":False,
    }

def assess_controlled_certification_readiness(
    *,
    preflight:dict[str,Any],
    evidence_manifest:dict[str,Any],
    human_authorized:bool,
) -> dict[str,Any]:
    if preflight.get("decision")!="PASS":
        return {
            "decision":"HOLD",
            "reason":"CUTOVER_PREFLIGHT_NOT_PASS",
            "controlled_live_certification_ready":False,
            "public_launch_authority":False,
        }
    missing=[k for k,v in (evidence_manifest.get("evidence") or {}).items() if not v]
    if missing:
        return {
            "decision":"HOLD",
            "reason":"LIVE_EVIDENCE_INCOMPLETE",
            "missing":missing,
            "controlled_live_certification_ready":False,
            "public_launch_authority":False,
        }
    if human_authorized is not True:
        return {
            "decision":"HOLD",
            "reason":"EXPLICIT_HUMAN_AUTHORITY_REQUIRED",
            "controlled_live_certification_ready":False,
            "public_launch_authority":False,
        }
    return {
        "decision":"READY_FOR_BOUNDED_LIVE_CERTIFICATION",
        "controlled_live_certification_ready":True,
        "public_launch_authority":False,
        "production_deploy_authority":False,
        "customer_charging_authority":"SEPARATE_GATE_REQUIRED",
    }
