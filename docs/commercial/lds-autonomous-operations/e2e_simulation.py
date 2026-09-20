#!/usr/bin/env python3
from pathlib import Path
from dataclasses import asdict
from typing import Dict, List
import importlib.util
import json

ROOT=Path(__file__).resolve().parent
LIFECYCLE=ROOT.parent/"lds-integrated-customer-lifecycle-gate"/"lifecycle_gate.py"

spec=importlib.util.spec_from_file_location("lifecycle_gate",LIFECYCLE)
lc=importlib.util.module_from_spec(spec)
spec.loader.exec_module(lc)

from engine import AutoKickoffEvidence, auto_kickoff, OutcomeSnapshot, outcome_decision, ProjectState, no_idle_check
from intent_compiler import IntentPackage, compile_work_package
from completion_gate import CompletionEvidence, evaluate_completion
from governance_closure import (
    PolicyDecision, evaluate_policy, AccessLeaseRequest, broker_access,
    ProvenanceEvidence, provenance_gate, PortabilityEvidence, portability_gate,
    BusinessHealth, business_health_governor
)

def _transition(fr,to,evidence,deps,human,key):
    return lc.evaluate_transition(lc.TransitionRequest(
        org_id="SIM-CUSTOMER-001",
        from_state=fr,
        to_state=to,
        evidence=frozenset(evidence),
        dependencies=deps,
        authority=lc.AuthorityReceipt(
            org_id="SIM-CUSTOMER-001",
            actor_id="sim-human" if human else "ld-autonomous-orchestrator",
            approved_at="2026-09-20T13:00:00Z",
            human_approved=human,
            evidence_refs=tuple(sorted(evidence)),
            idempotency_key=key
        )
    ))

def run_simulation(order:Dict)->Dict:
    events=[]
    ld_human_gates=[]
    customer_actions=[]

    def add(stage,result,actor="LD_AUTO"):
        events.append({"stage":stage,"actor":actor,**result})
        if result.get("status")=="HUMAN_GATE" and actor!="CUSTOMER":
            ld_human_gates.append(stage)

    add("POLICY_PRECHECK",evaluate_policy(PolicyDecision(
        "autonomy-policy-v1","standard_ld_launch",True,"NON_PRODUCTION","LOW",True
    )))

    c=order["commercial_evidence"]
    transitions=[
      ("VISITOR","ASSESSMENT",["legitimate_lead_evidence"],{},False),
      ("ASSESSMENT","QUALIFIED",["assessment_complete","market_supported"],{"workflow_assessment":True,"global_commerce_readiness":True},False),
      ("QUALIFIED","BLUEPRINT_APPROVED",["approved_scope"],{"system_blueprint":True},True),
      ("BLUEPRINT_APPROVED","QUOTATION_APPROVED",["pricing_reviewed","human_approved_quotation"],{"pricing_estimation_intelligence":True,"commercial_document_system":True},True),
      ("QUOTATION_APPROVED","CONTRACT_ACCEPTED",["digital_acceptance_evidence"],{"contract_digital_acceptance":True},False),
      ("CONTRACT_ACCEPTED","PAYMENT_RECONCILED",["authoritative_payment_reconciliation"],{"customer_fraud_payment_abuse":True,"commercial_document_lifecycle":True},False),
    ]
    for idx,(fr,to,ev,deps,human) in enumerate(transitions,1):
        result=_transition(fr,to,ev,deps,human,f"SIM-{idx}")
        add(f"{fr}_TO_{to}",result,"LD_HUMAN" if human else "LD_AUTO")
        if human:
            ld_human_gates.append(f"{fr}_TO_{to}")

    compiled=compile_work_package(IntentPackage(
        objective=order["objective"],
        capability_id=order["capability_id"],
        scope_version=1,
        requirements_confirmed=True,
        approved_scope=True,
        must_have=order["must_have"],
        acceptance_criteria=order["acceptance_criteria"],
        dependencies=order["dependencies"],
        exclusions=order["exclusions"],
        unresolved_questions=[]
    ))
    add("INTENT_TO_EXECUTION",compiled)

    kickoff=auto_kickoff(AutoKickoffEvidence(
        payment_reconciled=True,confirmed_requirement_scope=True,
        capability_id=order["capability_id"],capacity_available=True,unit_economics_status="PASS"
    ))
    add("AUTO_KICKOFF_ELIGIBILITY",kickoff)

    kickoff_transition=_transition(
        "PAYMENT_RECONCILED","KICKOFF_APPROVED",
        ["kickoff_ready","autonomous_kickoff_eligibility"],
        {"customer_onboarding":True,"autonomous_operations":True},False,"SIM-7"
    )
    add("PAYMENT_RECONCILED_TO_KICKOFF_APPROVED",kickoff_transition)

    build_transition=_transition(
        "KICKOFF_APPROVED","BUILDING",["scope_snapshot_current"],{},False,"SIM-8"
    )
    add("KICKOFF_APPROVED_TO_BUILDING",build_transition)

    add("JIT_BUILD_ACCESS",broker_access(AccessLeaseRequest("nonproduction_build","SIM-TASK-1",True,20,30)))

    add("NO_IDLE_BUILD_CHECK",no_idle_check(ProjectState("BUILDING",next_trigger="AUTOMATED_QA")))

    build_complete=_transition(
        "BUILDING","QA_PASSED",["build_complete","qa_evidence"],{},False,"SIM-9"
    )
    add("BUILDING_TO_QA_PASSED",build_complete)

    completion=evaluate_completion(CompletionEvidence(
        target_state="QA_PASSED",
        required_criteria=order["acceptance_criteria"],
        passed_criteria=order["acceptance_criteria"],
        evidence_refs=["qa-run-SIM-001","artifact-SIM-001"],
        artifact_digest_present=True,
        regression_pass=True
    ))
    add("EVIDENCE_COMPLETION_GATE",completion)

    provenance=provenance_gate(ProvenanceEvidence(
        True,True,True,True,True,True,True
    ))
    add("SUPPLY_CHAIN_PROVENANCE",provenance)

    customer_actions.append("CUSTOMER_UAT_ACCEPTANCE")
    outcome=outcome_decision(OutcomeSnapshot(
        order["acceptance_criteria"],order["acceptance_criteria"],True,True
    ))
    add("CUSTOMER_OUTCOME_ACCEPTANCE",outcome,"CUSTOMER")

    accepted=_transition(
        "QA_PASSED","CUSTOMER_ACCEPTED",["customer_acceptance_evidence"],{},False,"SIM-10"
    )
    add("QA_PASSED_TO_CUSTOMER_ACCEPTED",accepted)

    delivered=_transition(
        "CUSTOMER_ACCEPTED","DELIVERED",["delivery_evidence"],{},False,"SIM-11"
    )
    add("CUSTOMER_ACCEPTED_TO_DELIVERED",delivered)

    portability=portability_gate(PortabilityEvidence(True,True,True,True,True,True))
    add("PORTABILITY_EXIT_GATE",portability)

    health=business_health_governor(BusinessHealth(
        True,"HEALTHY","AVAILABLE","HEALTHY","NORMAL","LOW",False
    ))
    add("BUSINESS_HEALTH_GOVERNOR",health)

    failures=[e for e in events if e.get("status") in {"HOLD","HUMAN_GATE"} and e["actor"]!="LD_HUMAN"]
    idle_failures=[e for e in events if e.get("reason")=="IDLE_WITHOUT_DOCUMENTED_REASON"]
    unsafe=[e for e in events if e.get("production_authority") is True]

    ld_human_touchpoints=sorted(set(ld_human_gates))
    result={
        "order_id":order["order_id"],
        "scenario":order["scenario"],
        "environment":order["environment"],
        "final_state":"DELIVERED" if not failures else "BLOCKED",
        "events":events,
        "metrics":{
            "total_events":len(events),
            "ld_human_touchpoints":len(ld_human_touchpoints),
            "customer_action_touchpoints":len(customer_actions),
            "idle_failures":len(idle_failures),
            "unsafe_authority_events":len(unsafe),
            "unexpected_failures":len(failures),
        },
        "ld_human_gate_stages":ld_human_touchpoints,
        "customer_action_stages":customer_actions,
        "observed_bottlenecks":[
            "BLUEPRINT_APPROVAL_REMAINS_HUMAN",
            "QUOTATION_APPROVAL_REMAINS_HUMAN"
        ],
        "production_executed":False
    }
    return result

if __name__=="__main__":
    order=json.loads((ROOT/"sample_order.json").read_text())
    print(json.dumps(run_simulation(order),indent=2,sort_keys=True))
