import json
from pathlib import Path

from ready_business_p3 import (
    evaluate_controlled_transaction_prereqs,
    create_revenue_readiness_packet,
    record_real_transaction_evidence,
    record_unit_economics,
    assess_real_revenue_proof,
    make_synthetic_readiness_fixture,
)

ROOT=Path(__file__).resolve().parents[2]
SNAPSHOT=json.loads((ROOT/"docs/commercial/LDS_ACTIVATION_SNAPSHOT.json").read_text())

def packet():
    return create_revenue_readiness_packet(prospect_ref="prospect-fixture-001",project_id="LD-FIXTURE-001")

def real_evidence():
    return {
        "qualified_lead_ref":"e:lead","approved_quotation_ref":"e:quote",
        "customer_acceptance_ref":"e:acceptance","controlled_transaction_authority_ref":"e:authority",
        "provider_payment_ref":"e:payment","signed_webhook_ref":"e:webhook",
        "paid_order_ref":"e:order","delivery_ref":"e:delivery",
        "invoice_or_receipt_ref":"e:receipt","reconciliation_ref":"e:reconciliation",
    }

def economics(p):
    return record_unit_economics(
        p,marketing_cost=10,delivery_cost=50,payment_fee=3,setup_minutes=45,support_minutes=15,
        evidence_refs={
            "marketing_cost_ref":"e:mkt","delivery_cost_ref":"e:delivery-cost",
            "payment_fee_ref":"e:fee","setup_time_ref":"e:setup-time","support_time_ref":"e:support-time",
        },
    )

def test_current_activation_snapshot_holds():
    r=evaluate_controlled_transaction_prereqs(SNAPSHOT)
    assert r["decision"]=="HOLD"
    assert "LD_DEDICATED_BUSINESS_PHONE_VERIFIED" in json.dumps(r)
    assert r["production_mutation_performed"] is False

def test_packet_is_pre_activation_and_locked():
    p=packet()
    assert p["decision"]=="ALLOW"
    assert p["payment_activation"]=="HOLD"
    assert p["production"]=="LOCKED"
    assert p["real_revenue_proof"] is False
    assert all(v is None for v in p["evidence"].values())

def test_incomplete_real_evidence_holds():
    p=packet()
    r=record_real_transaction_evidence(
        p,evidence={"qualified_lead_ref":"e:lead"},quotation_amount=199,provider_payment_amount=199,real_customer=True
    )
    assert r["decision"]=="HOLD" and r["reason"]=="REAL_EVIDENCE_INCOMPLETE"

def test_amount_mismatch_holds():
    r=record_real_transaction_evidence(
        packet(),evidence=real_evidence(),quotation_amount=199,provider_payment_amount=198,real_customer=True
    )
    assert r["reason"]=="AMOUNT_MISMATCH"

def test_synthetic_fixture_never_becomes_real_revenue_proof():
    p=make_synthetic_readiness_fixture(packet())
    r=assess_real_revenue_proof(p,controlled_prereq_decision="PASS")
    assert r["decision"]=="READINESS_PASS" and r["real_revenue_proof"] is False

def test_real_proof_holds_while_prereqs_hold():
    p=record_real_transaction_evidence(
        packet(),evidence=real_evidence(),quotation_amount=199,provider_payment_amount=199,real_customer=True
    )
    p=economics(p)
    r=assess_real_revenue_proof(p,controlled_prereq_decision="HOLD")
    assert r["decision"]=="HOLD" and r["real_revenue_proof"] is False

def test_complete_algorithm_passes_but_grants_no_launch_authority():
    p=record_real_transaction_evidence(
        packet(),evidence=real_evidence(),quotation_amount=199,provider_payment_amount=199,refund_amount=0,real_customer=True
    )
    p=economics(p)
    r=assess_real_revenue_proof(p,controlled_prereq_decision="PASS")
    assert r["decision"]=="PASS" and r["real_revenue_proof"] is True
    assert r["attributable_revenue"]==199
    assert r["commercial_contribution"]==136
    assert r["public_launch_authority"] is False
    assert len(r["evidence_digest"])==64

if __name__=="__main__":
    ts=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in ts:t()
    print(f"PASS {len(ts)} LD Ready Business Kit P3 tests")
