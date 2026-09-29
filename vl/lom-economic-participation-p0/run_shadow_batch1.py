#!/usr/bin/env python3
from __future__ import annotations

import json
from engine import FundingAllocation, WorkerProfile, Task, QAResult, transition_task, create_payable_entitlement
from shadow_pilot import evaluate_batch

def qa_pass(i: int) -> QAResult:
    return QAResult(
        qa_result_id=f"qa-pass-{i}",
        factual_consistency=30,
        hook_quality=13,
        clarity_readability=13,
        message_focus=9,
        cta_quality=9,
        duration_format=5,
        tone_audience_fit=5,
        policy_safety=10,
        confidence=0.95,
    )

def qa_revision(i: int) -> QAResult:
    return QAResult(
        qa_result_id=f"qa-rev-{i}",
        factual_consistency=30,
        hook_quality=10,
        clarity_readability=10,
        message_focus=7,
        cta_quality=6,
        duration_format=4,
        tone_audience_fit=4,
        policy_safety=9,
        confidence=0.90,
    )

def run_one(i: int, revision: bool) -> dict:
    fund = FundingAllocation(f"fund-{i}", approved_minor=1000, reserved_minor=500)
    worker = WorkerProfile(f"worker-{i}")
    task = Task(f"task-{i}", funding_id=fund.funding_id, worker_fee_minor=500)

    assert transition_task(task,"FUND_CONFIRMED","FINANCE",funding=fund)["decision"] == "ALLOW"
    assert transition_task(task,"MARK_READY","SYSTEM",funding=fund)["decision"] == "ALLOW"
    assert transition_task(task,"ASSIGN_WORKER","SYSTEM",worker=worker)["decision"] == "ALLOW"
    assert transition_task(task,"START_TASK","WORKER",worker=worker)["decision"] == "ALLOW"
    assert transition_task(task,"SUBMIT_WORK","WORKER",worker=worker)["decision"] == "ALLOW"
    assert transition_task(task,"START_QA","QA_SERVICE")["decision"] == "ALLOW"

    first_pass = not revision
    if revision:
        assert transition_task(task,"QA_REVISION","QA_SERVICE",qa=qa_revision(i))["decision"] == "ALLOW"
        assert transition_task(task,"START_REVISION","WORKER",worker=worker)["decision"] == "ALLOW"
        assert transition_task(task,"SUBMIT_WORK","WORKER",worker=worker)["decision"] == "ALLOW"
        assert transition_task(task,"START_QA","QA_SERVICE")["decision"] == "ALLOW"

    assert transition_task(task,"QA_PASS","QA_SERVICE",qa=qa_pass(i))["decision"] == "ALLOW"
    assert transition_task(task,"CREATE_PAYABLE","FINANCE",funding=fund)["decision"] == "ALLOW"
    entitlement = create_payable_entitlement(task,fund)

    return {
        "task_id": task.task_id,
        "synthetic": True,
        "first_pass": first_pass,
        "final_pass": True,
        "revision_count": task.revision_count,
        "human_intervention": False,
        "serious_fact_errors": 0,
        "duplicate_entitlements": 0,
        "unfunded_entitlements": 0,
        "unauthorized_transitions": 0,
        "minutes": 7 + (i % 4),
        "entitlement_status": entitlement.status,
        "actual_payout_executed": False,
        "production_authority": "NONE",
    }

def main() -> None:
    rows = [run_one(i, revision=(i >= 8)) for i in range(10)]
    result = evaluate_batch(rows)
    assert result["gate"]["decision"] == "READY_FOR_HUMAN_GO_NO_GO"
    out = {
        "schema": "lom.economic-participation.shadow-pilot/1",
        "batch": 1,
        "task_count": len(rows),
        "mode": "SYNTHETIC_NON_PRODUCTION",
        "tasks": rows,
        "result": result,
        "claims": {
            "real_customer_evidence": False,
            "real_worker_evidence": False,
            "real_revenue_evidence": False,
            "real_payout_evidence": False
        },
        "next_authority": "HUMAN_ONLY",
        "next_action": "REVIEW_SHADOW_BATCH_1_BEFORE_ANY_LIVE_PILOT"
    }
    print(json.dumps(out, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
