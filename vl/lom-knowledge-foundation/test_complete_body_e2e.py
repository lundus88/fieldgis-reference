from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
KNOW=ROOT/"vl/lom-knowledge-foundation"
sys.path.insert(0,str(KNOW))
from orchestrator_binding import bind_knowledge_to_objective

spec=importlib.util.spec_from_file_location("gate_e",ROOT/"vl/lom-gate-e-orchestrator/orchestrator.py")
gate_e=importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["gate_e"]=gate_e
spec.loader.exec_module(gate_e)


def h(text:str)->str:
    return sha256(text.encode()).hexdigest()


def knowledge_registry(conflict=False):
    rows=[{
      "name":"Official Fixture A","domain":"cadastral","jurisdiction":"SABAH",
      "source":"official:a","provenance":"controlled-test","authority_level":"AUTHORITATIVE_OFFICIAL",
      "version_or_date":"2026-09-24","status":"CURRENT","superseded_by":None,
      "confidence":0.99,"tags":["boundary"],"location":"fixture://official-a",
      "claim_key":"boundary-rule","content_digest":"sha256:"+"a"*64,
    }]
    if conflict:
        rows.append({
          **rows[0],
          "name":"Official Fixture B","source":"official:b","location":"fixture://official-b",
          "content_digest":"sha256:"+"b"*64,
        })
    return {"records":rows}


def run_controlled(*, knowledge_conflict=False, execution_ok=True, validation_ok=True, remediation_ok=True, revalidation_ok=True):
    audit=[]
    sensed={
      "signal_id":"sense-1","domain":"cadastral","jurisdiction":"SABAH",
      "intent":"prepare non-production cadastral validation change","risk":"LOW",
    }
    audit.append(("SENSE",sensed))

    reasoned={
      "objective_id":"obj-e2e-1",
      "requested_actions":["NON_PROD_CODE"],
      "delegated_actions":["NON_PROD_CODE"],
      "risk":"LOW","production":False,"reversible":True,
      "executor":"SANDBOX_EXECUTOR","validator":"INDEPENDENT_VALIDATOR",
      "evidence_refs":["evidence:"+h(str(sensed))],
    }
    audit.append(("REASON",reasoned))

    bound=bind_knowledge_to_objective(
      registry=knowledge_registry(knowledge_conflict),
      objective=reasoned,
      domain=sensed["domain"],jurisdiction=sensed["jurisdiction"],tags=("boundary",),
    )
    audit.append(("RETRIEVE_KNOWLEDGE",bound))
    if bound["decision"]!="ALLOW":
        return {"status":"HOLD","reason":bound["reason"],"audit":audit,"rollback":"NOT_REQUIRED","escalation":"KNOWLEDGE_AUTHORITY_REVIEW"}

    plan={"steps":["sandbox_execute","independent_validate","record_evidence"],"production_locked":True}
    audit.append(("PLAN",plan))

    obj=gate_e.Objective(**{
      k:bound["objective"][k] for k in (
        "objective_id","requested_actions","evidence_refs","delegated_actions","risk","production","reversible","executor","validator"
      )
    })
    outcome=gate_e.orchestrate(
      obj,
      execution_ok=execution_ok,
      validation_ok=validation_ok,
      remediation_ok=remediation_ok,
      revalidation_ok=revalidation_ok,
    )
    audit.append(("EXECUTE_VALIDATE_RECOVER",{
      "state":outcome.state,"stage":outcome.stage,"reasons":outcome.reasons,
      "production_locked":True,
    }))
    rollback="READY" if not execution_ok or not validation_ok else "NOT_REQUIRED"
    escalation="HUMAN_REVIEW" if outcome.state=="ESCALATE" else "NONE"
    final={
      "status":outcome.state,
      "reason":outcome.reasons[-1] if outcome.reasons else "VALIDATED_SUCCESS",
      "evidence_refs":outcome.evidence_refs,
      "rollback":rollback,
      "escalation":escalation,
      "production_authority":"HUMAN_ONLY",
      "protected_main_merge":"HUMAN_ONLY",
    }
    audit.append(("AUDIT_RESULT",final))
    return {**final,"audit":audit}


def test_happy_path_closes_full_loop_without_production_authority():
    r=run_controlled()
    assert r["status"]=="COMPLETE"
    assert r["production_authority"]=="HUMAN_ONLY"
    assert [x[0] for x in r["audit"]]==[
      "SENSE","REASON","RETRIEVE_KNOWLEDGE","PLAN","EXECUTE_VALIDATE_RECOVER","AUDIT_RESULT"
    ]


def test_source_conflict_fails_closed_before_execution():
    r=run_controlled(knowledge_conflict=True)
    assert r["status"]=="HOLD"
    assert r["reason"]=="SOURCE_CONFLICT"
    assert all(stage!="PLAN" for stage,_ in r["audit"])


def test_execution_failure_retries_only_via_governed_remediation():
    r=run_controlled(execution_ok=False,validation_ok=False,remediation_ok=True,revalidation_ok=True)
    assert r["status"]=="COMPLETE"
    assert r["reason"]=="REMEDIATED_AND_REVALIDATED"
    assert r["rollback"]=="READY"


def test_failed_remediation_escalates():
    r=run_controlled(execution_ok=False,validation_ok=False,remediation_ok=False)
    assert r["status"]=="ESCALATE"
    assert r["escalation"]=="HUMAN_REVIEW"


def test_failed_revalidation_escalates():
    r=run_controlled(execution_ok=True,validation_ok=False,remediation_ok=True,revalidation_ok=False)
    assert r["status"]=="ESCALATE"


if __name__=="__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests: t()
    print(f"PASS {len(tests)} complete-body controlled E2E tests")
