#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class DiagnosticEvidence:
    quotation_manual: bool
    followup_manual: bool
    customer_data_fragmented: bool
    website_not_generating_leads: bool
    repetitive_admin_work: bool
    reporting_manual_or_missing: bool
    no_customer_portal: bool
    no_workflow_automation: bool

WEIGHTS={
    "quotation_manual":12,
    "followup_manual":12,
    "customer_data_fragmented":14,
    "website_not_generating_leads":14,
    "repetitive_admin_work":14,
    "reporting_manual_or_missing":10,
    "no_customer_portal":10,
    "no_workflow_automation":14,
}

RECOMMENDATIONS={
    "quotation_manual":"Review quotation and commercial document automation",
    "followup_manual":"Review lead follow-up and CRM automation",
    "customer_data_fragmented":"Review a central customer/workflow data layer",
    "website_not_generating_leads":"Review conversion-focused website and lead capture",
    "repetitive_admin_work":"Review workflow automation for repetitive admin tasks",
    "reporting_manual_or_missing":"Review operational dashboard and reporting automation",
    "no_customer_portal":"Review a customer portal or self-service workflow",
    "no_workflow_automation":"Review an end-to-end automation opportunity map",
}

def assess(e:DiagnosticEvidence)->Dict:
    pain=[]
    for field,weight in WEIGHTS.items():
        if getattr(e,field):
            pain.append((field,weight))
    score=max(0,100-sum(weight for _,weight in pain))
    priorities=sorted(pain,key=lambda item:item[1],reverse=True)
    return {
        "digital_efficiency_score":score,
        "priority_opportunity_areas":[field for field,_ in priorities[:3]],
        "recommended_next_actions":[RECOMMENDATIONS[field] for field,_ in priorities[:3]],
        "advisory_only":True,
        "commercial_authority":False,
        "roi_guarantee":False,
    }
