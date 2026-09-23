import json
from pathlib import Path

from ready_business_p4 import (
    evaluate_cutover_preflight,
    kill_switch_matrix,
    validate_rollback_contract,
    build_customer_zero_rehearsal,
    build_future_live_evidence_manifest,
    assess_controlled_certification_readiness,
)

ROOT=Path(__file__).resolve().parents[2]
SNAPSHOT=json.loads((ROOT/"docs/commercial/LDS_ACTIVATION_SNAPSHOT.json").read_text())

def current_external():
    return {
        "DEDICATED_BUSINESS_PHONE":"IN_PROGRESS",
        "COMPANY_ACCOUNT":"IN_PROGRESS",
    }

def rollback_fixture():
    return {
        "candidate_deployment_ref":"synthetic:candidate",
        "known_good_deployment_ref":"synthetic:known-good",
        "lead_intake_disable_ref":"synthetic:lead-off",
        "checkout_disable_ref":"synthetic:checkout-off",
        "billing_disable_ref":"synthetic:billing-off",
        "incident_path_ref":"synthetic:incident",
        "rollback_procedure_ref":"synthetic:rollback",
    }

def fully_pass_snapshot():
    s=json.loads(json.dumps(SNAPSHOT))
    for section in ["business_licence","legal_trust","domain_email","lead_intake","payment"]:
        s.setdefault(section,{})["status"]="PASS"
    s["lead_intake"]["production_activation_authorized"]=True
    s["payment"]["production_activation_authorized"]=True
    return s

def test_current_external_gates_hold():
    r=evaluate_cutover_preflight(SNAPSHOT,external_gates=current_external())
    assert r["decision"]=="HOLD"
    txt=json.dumps(r)
    assert "DEDICATED_BUSINESS_PHONE" in txt
    assert "COMPANY_ACCOUNT" in txt
    assert r["production_mutation_performed"] is False
    assert r["live_payment_performed"] is False

def test_kill_switches_are_independent():
    m=kill_switch_matrix()
    assert m["independent_controls"] is True
    assert set(m["controls"])=={"lead_intake","checkout","billing","notification"}
    assert "informational_site" in m["controls"]["billing"]["preserves"]
    assert m["production_mutation_performed"] is False

def test_rollback_contract_fails_closed():
    r=validate_rollback_contract({"candidate_deployment_ref":"x"})
    assert r["decision"]=="HOLD"
    assert r["reason"]=="ROLLBACK_CONTRACT_INCOMPLETE"

def test_known_good_must_differ():
    c=rollback_fixture()
    c["known_good_deployment_ref"]=c["candidate_deployment_ref"]
    r=validate_rollback_contract(c)
    assert r["reason"]=="KNOWN_GOOD_MUST_DIFFER_FROM_CANDIDATE"

def test_customer_zero_is_synthetic_only():
    p=evaluate_cutover_preflight(SNAPSHOT,external_gates=current_external())
    r=build_customer_zero_rehearsal(preflight=p,rollback_contract=rollback_fixture())
    assert r["decision"]=="READINESS_PASS"
    assert r["synthetic_only"] is True
    assert r["real_customer"] is False
    assert r["payment_transactions"]==0
    assert r["production_mutations"]==0
    assert r["public_launch_authorized"] is False
    assert r["expected_live_action"]=="STOP_AT_HUMAN_GATE"

def test_future_manifest_starts_empty():
    m=build_future_live_evidence_manifest()
    assert m["status"]=="EMPTY_TEMPLATE"
    assert all(v is None for v in m["evidence"].values())
    assert m["production_authority"] is False

def test_even_full_simulated_preflight_needs_live_evidence_and_human_gate():
    p=evaluate_cutover_preflight(
        fully_pass_snapshot(),
        external_gates={"DEDICATED_BUSINESS_PHONE":"PASS","COMPANY_ACCOUNT":"PASS"},
    )
    assert p["decision"]=="PASS"
    m=build_future_live_evidence_manifest()
    r=assess_controlled_certification_readiness(
        preflight=p,evidence_manifest=m,human_authorized=True
    )
    assert r["decision"]=="HOLD"
    assert r["reason"]=="LIVE_EVIDENCE_INCOMPLETE"

def test_complete_fixture_only_reaches_bounded_certification_not_public_launch():
    p=evaluate_cutover_preflight(
        fully_pass_snapshot(),
        external_gates={"DEDICATED_BUSINESS_PHONE":"PASS","COMPANY_ACCOUNT":"PASS"},
    )
    m=build_future_live_evidence_manifest()
    m["evidence"]={k:f"fixture:{k}" for k in m["evidence"]}
    r=assess_controlled_certification_readiness(
        preflight=p,evidence_manifest=m,human_authorized=True
    )
    assert r["decision"]=="READY_FOR_BOUNDED_LIVE_CERTIFICATION"
    assert r["controlled_live_certification_ready"] is True
    assert r["public_launch_authority"] is False
    assert r["production_deploy_authority"] is False
    assert r["customer_charging_authority"]=="SEPARATE_GATE_REQUIRED"

if __name__=="__main__":
    ts=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in ts:t()
    print(f"PASS {len(ts)} LD Ready Business Kit P4 tests")
