#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List

SEVERITY_ORDER={"P3":0,"P2":1,"P1":2,"P0":3}

@dataclass(frozen=True)
class Signal:
    risk_id: str
    severity: str
    active: bool
    evidence_refs: tuple[str,...]=()
    customer_impact: bool=True

def evaluate(signals: List[Signal]) -> Dict:
    active=[s for s in signals if s.active]
    if not active:
        return {"status":"CLEAR","highest_severity":None,"actions":[]}

    for s in active:
        if s.severity not in SEVERITY_ORDER:
            raise ValueError("invalid severity")
        if not s.evidence_refs:
            return {
                "status":"HOLD",
                "highest_severity":s.severity,
                "actions":["COLLECT_EVIDENCE"],
                "reason":"ACTIVE_RISK_WITHOUT_EVIDENCE"
            }

    highest=max(active,key=lambda s:SEVERITY_ORDER[s.severity]).severity
    actions=[]
    if highest=="P0":
        actions += ["HUMAN_ESCALATION","CONTAIN_IF_APPLICABLE","CLIENT_STATUS_UPDATE"]
    elif highest=="P1":
        actions += ["OWNER_ASSIGN","MITIGATION_PLAN","CLIENT_STATUS_UPDATE"]
    elif highest=="P2":
        actions += ["PROACTIVE_UPDATE","CORRECT_WORKFLOW"]
    else:
        actions += ["TRACK"]

    if any(s.risk_id=="CDP-004" for s in active):
        actions += ["SET_CLIENT_ACTION_REQUIRED","REBASELINE_ETA"]
    if any(s.risk_id in {"CDP-008","CDP-010"} for s in active):
        actions += ["FREEZE_CONSEQUENTIAL_AUTOMATION"]

    return {
        "status":"AT_RISK" if highest in {"P0","P1"} else "WATCH",
        "highest_severity":highest,
        "actions":sorted(set(actions))
    }

def should_send_status(last_update_business_hours:int, active_risk:bool)->bool:
    if last_update_business_hours < 0:
        raise ValueError("invalid hours")
    if active_risk:
        return last_update_business_hours >= 4
    return last_update_business_hours >= 24
