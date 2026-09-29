#!/usr/bin/env python3
from __future__ import annotations

from statistics import median
from engine import evaluate_scale_gate

BATCHES = (10,20,30,40)

def aggregate(rows):
    total=len(rows)
    if total == 0:
        raise ValueError("NO_ROWS")
    first_pass=sum(1 for r in rows if r["first_pass"])/total
    final_pass=sum(1 for r in rows if r["final_pass"])/total
    revisions=sum(1 for r in rows if r["revision_count"]>0)/total
    human=sum(1 for r in rows if r["human_intervention"])/total
    return {
        "first_pass_rate": first_pass,
        "final_pass_rate": final_pass,
        "serious_fact_errors": sum(r["serious_fact_errors"] for r in rows),
        "revision_rate": revisions,
        "median_minutes": median(r["minutes"] for r in rows),
        "human_intervention_rate": human,
        "duplicate_entitlements": sum(r["duplicate_entitlements"] for r in rows),
        "unfunded_entitlements": sum(r["unfunded_entitlements"] for r in rows),
        "unauthorized_transitions": sum(r["unauthorized_transitions"] for r in rows),
        "synthetic_only": all(r.get("synthetic") is True for r in rows),
    }

def evaluate_batch(rows):
    metrics=aggregate(rows)
    return {"metrics":metrics,"gate":evaluate_scale_gate(metrics)}

def next_batch_size(completed):
    if completed not in BATCHES:
        return None
    i=BATCHES.index(completed)
    return BATCHES[i+1] if i+1 < len(BATCHES) else None
