#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict,Optional

GOOD_FRESHNESS={"CURRENT","RECENT"}

@dataclass(frozen=True)
class MetricEvidence:
    value: Optional[float]
    source_status: str
    freshness: str
    completeness_pct: float
    contradictory: bool=False

def normalize(name:str, e:MetricEvidence, min_completeness:float=90.0)->Dict:
    if e.contradictory:
        return {"metric":name,"status":"HOLD","reason":"CONTRADICTORY_EVIDENCE",
                "value":None,"source_status":e.source_status,"freshness":e.freshness,
                "evidence_completeness":e.completeness_pct}
    if e.source_status not in {"AUTHORITATIVE","VERIFIED"}:
        return {"metric":name,"status":"REVIEW","reason":"SOURCE_NOT_AUTHORITATIVE",
                "value":None,"source_status":e.source_status,"freshness":e.freshness,
                "evidence_completeness":e.completeness_pct}
    if e.freshness not in GOOD_FRESHNESS:
        return {"metric":name,"status":"REVIEW","reason":"STALE_EVIDENCE",
                "value":None,"source_status":e.source_status,"freshness":e.freshness,
                "evidence_completeness":e.completeness_pct}
    if e.completeness_pct < min_completeness:
        return {"metric":name,"status":"REVIEW","reason":"EVIDENCE_INCOMPLETE",
                "value":None,"source_status":e.source_status,"freshness":e.freshness,
                "evidence_completeness":e.completeness_pct}
    return {"metric":name,"status":"CONFIRMED","value":e.value,
            "source_status":e.source_status,"freshness":e.freshness,
            "evidence_completeness":e.completeness_pct}

def executive_view(metrics:Dict[str,MetricEvidence], exceptions:int=0)->Dict:
    required=["pipeline","revenue","margin","capacity","customer_health","recurring_revenue"]
    cards={k:normalize(k,metrics[k]) for k in required if k in metrics}
    missing=[k for k in required if k not in metrics]
    if missing:
        for k in missing:
            cards[k]={"metric":k,"status":"REVIEW","reason":"METRIC_EVIDENCE_MISSING","value":None}
    if any(v["status"]=="HOLD" for v in cards.values()):
        overall="HOLD"
    elif any(v["status"]=="REVIEW" for v in cards.values()) or exceptions>0:
        overall="HUMAN_REVIEW"
    else:
        overall="CURRENT"
    return {
      "schema":"lds.executive-commercial-mission-control/1",
      "overall":overall,
      "panels":cards,
      "risk_and_exceptions":{"open_exception_count":exceptions,
                             "status":"HUMAN_REVIEW" if exceptions>0 else "CLEAR"},
      "execution_authority":"NONE",
      "production_authority":"HUMAN_ONLY"
    }

def can_execute_commercial_action()->bool:
    return False
