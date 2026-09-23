from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

REAL_EVIDENCE_FIELDS = [
    "qualified_lead_ref",
    "approved_quotation_ref",
    "customer_acceptance_ref",
    "controlled_transaction_authority_ref",
    "provider_payment_ref",
    "signed_webhook_ref",
    "paid_order_ref",
    "delivery_ref",
    "invoice_or_receipt_ref",
    "reconciliation_ref",
]

CONTROLLED_TRANSACTION_PREREQS = {
    "business_licence": "PASS",
    "legal_trust": "PASS",
    "domain_email": "PASS",
    "lead_intake": "PASS",
    "payment": "PASS",
}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def evaluate_controlled_transaction_prereqs(snapshot: dict[str, Any]) -> dict[str, Any]:
    missing=[]
    for section, required in CONTROLLED_TRANSACTION_PREREQS.items():
        actual=(snapshot.get(section) or {}).get("status")
        if actual != required:
            missing.append({"section":section,"required":required,"actual":actual})

    legal=(snapshot.get("legal_trust") or {})
    if "LD_DEDICATED_BUSINESS_PHONE_VERIFIED" in (legal.get("remaining_particulars") or []):
        missing.append({
            "section":"legal_trust",
            "required":"LD_DEDICATED_BUSINESS_PHONE_VERIFIED",
            "actual":"PENDING",
        })

    if (snapshot.get("lead_intake") or {}).get("production_activation_authorized") is not True:
        missing.append({
            "section":"lead_intake",
            "required":"controlled Production authority",
            "actual":"NOT_AUTHORIZED",
        })
    if (snapshot.get("payment") or {}).get("production_activation_authorized") is not True:
        missing.append({
            "section":"payment",
            "required":"controlled Production authority",
            "actual":"NOT_AUTHORIZED",
        })

    return {
        "decision":"PASS" if not missing else "HOLD",
        "schema":"ld.controlled-transaction-prereq/1",
        "missing":missing,
        "public_launch_authorized":False,
        "production_mutation_performed":False,
    }

def create_revenue_readiness_packet(*,prospect_ref:str,project_id:str,currency:str="MYR") -> dict[str,Any]:
    if not prospect_ref or not project_id:
        return {"decision":"HOLD","reason":"PROSPECT_AND_PROJECT_REQUIRED"}
    if currency != "MYR":
        return {"decision":"HOLD","reason":"P3_MULTI_CURRENCY_NOT_SUPPORTED"}
    seed={"prospect_ref":prospect_ref,"project_id":project_id,"currency":currency}
    transaction_ref="LD-REV-"+_digest(seed)[:16].upper()
    return {
        "decision":"ALLOW",
        "schema":"ld.revenue-readiness-packet/1",
        "transaction_ref":transaction_ref,
        "prospect_ref":prospect_ref,
        "project_id":project_id,
        "currency":currency,
        "stage":"PRE_ACTIVATION_READY",
        "evidence":{k:None for k in REAL_EVIDENCE_FIELDS},
        "amounts":{"quotation_amount":None,"provider_payment_amount":None,"refund_amount":0.0},
        "metrics":{
            "marketing_cost":None,"delivery_cost":None,"payment_fee":None,
            "setup_minutes":None,"support_minutes":None,
        },
        "repeat_upgrade_referral":{
            "repeat_signal":None,"upgrade_signal":None,"referral_signal":None,
        },
        "real_customer":None,
        "synthetic":False,
        "real_revenue_proof":False,
        "payment_activation":"HOLD",
        "production":"LOCKED",
        "customer_release_authority":"HUMAN_ONLY",
    }

def record_real_transaction_evidence(
    packet:dict[str,Any],*,evidence:dict[str,str],
    quotation_amount:float,provider_payment_amount:float,
    refund_amount:float=0.0,real_customer:bool,
) -> dict[str,Any]:
    if packet.get("decision")!="ALLOW":
        return {"decision":"HOLD","reason":"PACKET_NOT_READY"}
    if packet.get("synthetic") is True:
        return {"decision":"HOLD","reason":"SYNTHETIC_PACKET_CANNOT_BECOME_REAL_PROOF"}
    if real_customer is not True:
        return {"decision":"HOLD","reason":"REAL_CUSTOMER_REQUIRED"}
    missing=[k for k in REAL_EVIDENCE_FIELDS if not evidence.get(k)]
    if missing:
        return {"decision":"HOLD","reason":"REAL_EVIDENCE_INCOMPLETE","missing":missing}
    if not isinstance(quotation_amount,(int,float)) or quotation_amount <= 0:
        return {"decision":"HOLD","reason":"QUOTATION_AMOUNT_INVALID"}
    if not isinstance(provider_payment_amount,(int,float)) or provider_payment_amount <= 0:
        return {"decision":"HOLD","reason":"PAYMENT_AMOUNT_INVALID"}
    if round(float(quotation_amount),2) != round(float(provider_payment_amount),2):
        return {"decision":"HOLD","reason":"AMOUNT_MISMATCH"}
    if not isinstance(refund_amount,(int,float)) or refund_amount < 0 or refund_amount > provider_payment_amount:
        return {"decision":"HOLD","reason":"REFUND_AMOUNT_INVALID"}

    out=json.loads(json.dumps(packet))
    out["evidence"].update(evidence)
    out["amounts"]["quotation_amount"]=round(float(quotation_amount),2)
    out["amounts"]["provider_payment_amount"]=round(float(provider_payment_amount),2)
    out["amounts"]["refund_amount"]=round(float(refund_amount),2)
    out["real_customer"]=True
    out["stage"]="REAL_EVIDENCE_CAPTURED"
    return out

def record_unit_economics(
    packet:dict[str,Any],*,marketing_cost:float,delivery_cost:float,payment_fee:float,
    setup_minutes:int,support_minutes:int,evidence_refs:dict[str,str],
) -> dict[str,Any]:
    required_refs=["marketing_cost_ref","delivery_cost_ref","payment_fee_ref","setup_time_ref","support_time_ref"]
    missing=[k for k in required_refs if not evidence_refs.get(k)]
    if missing:
        return {"decision":"HOLD","reason":"UNIT_ECONOMICS_EVIDENCE_INCOMPLETE","missing":missing}
    vals=[marketing_cost,delivery_cost,payment_fee]
    if any(not isinstance(v,(int,float)) or v < 0 for v in vals):
        return {"decision":"HOLD","reason":"COST_INVALID"}
    if any(not isinstance(v,int) or v < 0 for v in [setup_minutes,support_minutes]):
        return {"decision":"HOLD","reason":"TIME_METRIC_INVALID"}
    out=json.loads(json.dumps(packet))
    out["metrics"]={
        "marketing_cost":round(float(marketing_cost),2),
        "delivery_cost":round(float(delivery_cost),2),
        "payment_fee":round(float(payment_fee),2),
        "setup_minutes":setup_minutes,
        "support_minutes":support_minutes,
        "evidence_refs":dict(evidence_refs),
    }
    return out

def assess_real_revenue_proof(packet:dict[str,Any],*,controlled_prereq_decision:str) -> dict[str,Any]:
    if packet.get("synthetic") is True:
        return {"decision":"READINESS_PASS","real_revenue_proof":False,"reason":"SYNTHETIC_FIXTURE_ONLY"}
    if controlled_prereq_decision != "PASS":
        return {
            "decision":"HOLD","real_revenue_proof":False,
            "reason":"CONTROLLED_TRANSACTION_PREREQUISITES_NOT_PASS",
        }
    if packet.get("real_customer") is not True:
        return {"decision":"HOLD","real_revenue_proof":False,"reason":"REAL_CUSTOMER_NOT_EVIDENCED"}
    missing=[k for k in REAL_EVIDENCE_FIELDS if not (packet.get("evidence") or {}).get(k)]
    if missing:
        return {"decision":"HOLD","real_revenue_proof":False,"reason":"REAL_EVIDENCE_INCOMPLETE","missing":missing}
    metrics=packet.get("metrics") or {}
    if any(metrics.get(k) is None for k in ["marketing_cost","delivery_cost","payment_fee","setup_minutes","support_minutes"]):
        return {"decision":"HOLD","real_revenue_proof":False,"reason":"UNIT_ECONOMICS_INCOMPLETE"}

    paid=float(packet["amounts"]["provider_payment_amount"])
    refund=float(packet["amounts"].get("refund_amount") or 0)
    contribution=round(
        paid-refund-float(metrics["marketing_cost"])-float(metrics["delivery_cost"])-float(metrics["payment_fee"]),2
    )
    evidence_body={
        "transaction_ref":packet["transaction_ref"],
        "project_id":packet["project_id"],
        "currency":packet["currency"],
        "paid":paid,
        "refund":refund,
        "commercial_contribution":contribution,
        "evidence":packet["evidence"],
        "metrics":metrics,
    }
    return {
        "decision":"PASS",
        "real_revenue_proof":True,
        "schema":"ld.real-revenue-proof/1",
        "transaction_ref":packet["transaction_ref"],
        "attributable_revenue":round(paid-refund,2),
        "commercial_contribution":contribution,
        "currency":packet["currency"],
        "evidence_digest":_digest(evidence_body),
        "public_launch_authority":False,
    }

def make_synthetic_readiness_fixture(packet:dict[str,Any]) -> dict[str,Any]:
    out=json.loads(json.dumps(packet))
    out["synthetic"]=True
    out["real_customer"]=False
    out["stage"]="SYNTHETIC_DRY_RUN"
    for k in REAL_EVIDENCE_FIELDS:
        out["evidence"][k]=f"synthetic:{k}"
    out["amounts"]["quotation_amount"]=199.0
    out["amounts"]["provider_payment_amount"]=199.0
    out["metrics"]={
        "marketing_cost":0.0,"delivery_cost":50.0,"payment_fee":3.0,
        "setup_minutes":45,"support_minutes":15,
        "evidence_refs":{
            "marketing_cost_ref":"synthetic:marketing",
            "delivery_cost_ref":"synthetic:delivery",
            "payment_fee_ref":"synthetic:fee",
            "setup_time_ref":"synthetic:setup",
            "support_time_ref":"synthetic:support",
        },
    }
    out["real_revenue_proof"]=False
    return out
