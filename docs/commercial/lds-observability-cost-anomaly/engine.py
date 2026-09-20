#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

@dataclass(frozen=True)
class Metric:
    current:float
    baseline:float
    warning_pct:float
    critical_pct:float
    evidence_current:bool
    tenant_match:bool
    baseline_version:str

def assess(m:Metric)->Dict:
    if not m.tenant_match:
        return {"status":"HOLD","risk_flags":["TENANT_MISMATCH"],"remediation_authorized":False}
    if not m.evidence_current or not m.baseline_version:
        return {"status":"REVIEW","risk_flags":["EVIDENCE_OR_BASELINE_NOT_CURRENT"],"remediation_authorized":False}
    if m.baseline < 0 or m.warning_pct < 0 or m.critical_pct < m.warning_pct:
        return {"status":"REVIEW","risk_flags":["INVALID_THRESHOLD_POLICY"],"remediation_authorized":False}
    if m.baseline == 0:
        deviation = 0.0 if m.current == 0 else 100.0
    else:
        deviation=((m.current-m.baseline)/abs(m.baseline))*100.0
    magnitude=abs(deviation)
    status="NORMAL"
    if magnitude >= m.critical_pct:
        status="CRITICAL_ANOMALY"
    elif magnitude >= m.warning_pct:
        status="WARNING_ANOMALY"
    return {
      "status":status,
      "deviation_pct":round(deviation,2),
      "root_cause_confirmed":False,
      "remediation_authorized":False,
      "automatic_shutdown":False,
      "automatic_price_change":False
    }

def automatic_shutdown_allowed()->bool:
    return False
