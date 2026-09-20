#!/usr/bin/env python3
from dataclasses import dataclass
from typing import List,Dict

@dataclass(frozen=True)
class Blueprint:
    problem_statement:str
    proposed_workflow:str
    modules:tuple[str,...]
    acceptance_criteria:tuple[str,...]
    dependencies:tuple[str,...]=()
    unresolved_assumptions:tuple[str,...]=()
    customer_approved:bool=False
    mode:str="LIGHTWEIGHT_FREE"

def assess(b:Blueprint)->Dict:
    if b.mode not in {"LIGHTWEIGHT_FREE","PAID_DISCOVERY"}:
        return {"status":"HOLD","reason":"INVALID_DISCOVERY_MODE"}
    if not b.problem_statement.strip() or not b.proposed_workflow.strip():
        return {"status":"NEED_MORE_INFO","reason":"CORE_SCOPE_MISSING"}
    if not b.modules or not b.acceptance_criteria:
        return {"status":"NEED_MORE_INFO","reason":"MODULES_OR_ACCEPTANCE_MISSING"}
    if b.unresolved_assumptions:
        return {"status":"REVIEW","reason":"UNRESOLVED_ASSUMPTIONS","quote_ready":False}
    return {
      "status":"APPROVED_SCOPE" if b.customer_approved else "READY_FOR_CUSTOMER_REVIEW",
      "quote_ready":bool(b.customer_approved),
      "build_authorized":False,
      "binding_price_created":False
    }

def freeze_snapshot(b:Blueprint,version:int)->Dict:
    if version<1: raise ValueError("version must be positive")
    if not b.customer_approved: return {"decision":"HOLD","reason":"CUSTOMER_APPROVAL_REQUIRED"}
    return {"decision":"FREEZE","version":version,"immutable_after_approval":True,"changes_require":"CHANGE_REQUEST"}
