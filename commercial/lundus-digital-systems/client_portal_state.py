#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Optional, Dict

@dataclass(frozen=True)
class PortalEvidence:
    customer_authorized: bool
    project_state: str
    project_evidence_current: bool
    quote_status: str
    invoice_status: str
    payment_status: str
    payment_verified: bool
    receipt_issued: bool
    milestone_funded: bool
    build_status: str
    qa_status: str
    qa_evidence: bool
    uat_status: str
    uat_evidence: bool
    delivery_status: str
    delivery_evidence: bool
    production_deployed_evidence: bool

def compose(e:PortalEvidence)->Dict:
    if not e.customer_authorized:
        return {"portal_status":"DENY","reason":"CUSTOMER_NOT_AUTHORIZED"}
    if not e.project_evidence_current:
        return {"portal_status":"REVIEW","reason":"STALE_OR_MISSING_PROJECT_EVIDENCE"}

    payment="PAID" if e.payment_status=="paid" and e.payment_verified else ("REVIEW" if e.payment_status=="paid" else e.payment_status.upper())
    qa="PASS" if e.qa_status=="passed" and e.qa_evidence else ("REVIEW" if e.qa_status=="passed" else e.qa_status.upper())
    uat="ACCEPTED" if e.uat_status=="accepted" and e.uat_evidence else ("REVIEW" if e.uat_status=="accepted" else e.uat_status.upper())
    delivery="DELIVERED" if e.delivery_status=="delivered" and e.delivery_evidence else ("REVIEW" if e.delivery_status=="delivered" else e.delivery_status.upper())

    build=e.build_status.upper()
    if build in {"SUCCEEDED","CERTIFIED"} and not e.production_deployed_evidence:
        production="NOT_PROVEN"
    else:
        production="DEPLOYED" if e.production_deployed_evidence else "NOT_DEPLOYED"

    return {
      "portal_status":"READY",
      "project_status":e.project_state,
      "commercial":{
        "quote":e.quote_status.upper(),
        "invoice":e.invoice_status.upper(),
        "payment":payment,
        "receipt":"ISSUED" if e.receipt_issued and payment=="PAID" else ("REVIEW" if e.receipt_issued else "NOT_ISSUED")
      },
      "delivery":{
        "milestone":"FUNDED" if e.milestone_funded and payment=="PAID" else "NOT_FUNDED",
        "build":build,
        "qa":qa,
        "uat":uat,
        "delivery":delivery,
        "production":production
      }
    }

def can_mutate_state()->bool:
    return False
