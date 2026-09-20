#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass(frozen=True)
class TransactionEvidence:
    customer_country: str
    merchant_country: str
    currency: str
    market_supported: bool
    fx_rate: Optional[float]=None
    fx_source: Optional[str]=None
    fx_current: bool=False
    tax_evidence_present: bool=False
    compliance_evidence_current: bool=False

def assess(e: TransactionEvidence)->Dict:
    flags=[]
    if not e.market_supported:
        return {"status":"HOLD","risk_flags":["UNSUPPORTED_MARKET"],"human_review_required":True,"customer_charge_authorized":False}
    if not e.compliance_evidence_current:
        flags.append("COMPLIANCE_EVIDENCE_MISSING_OR_STALE")
    if not e.tax_evidence_present:
        flags.append("TAX_EVIDENCE_MISSING")
    if e.fx_rate is not None:
        if e.fx_rate <= 0 or not e.fx_source or not e.fx_current:
            flags.append("FX_EVIDENCE_INVALID_OR_STALE")
    elif e.currency.upper() != "MYR":
        flags.append("FX_EVIDENCE_MISSING")
    status="READY_FOR_HUMAN_REVIEW" if not flags else "REVIEW"
    return {"status":status,"risk_flags":flags,"human_review_required":True,"customer_charge_authorized":False}

def invented_fx_allowed()->bool:
    return False
