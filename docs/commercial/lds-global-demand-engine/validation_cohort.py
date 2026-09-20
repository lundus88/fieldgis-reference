#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class Cohort:
    relevant_visitors:int
    qualified_leads:int
    quotations:int
    paid_customers:int
    accepted_deliveries:int
    referrals:int=0
    repeat_or_expansion:int=0
    case_studies:int=0
    spend:float=0.0

def _rate(num:int,den:int)->Optional[float]:
    if den<=0:
        return None
    return round(num/den,4)

def evaluate_cohort(c:Cohort)->Dict:
    rates={
        "visitor_to_qualified":_rate(c.qualified_leads,c.relevant_visitors),
        "qualified_to_quotation":_rate(c.quotations,c.qualified_leads),
        "quotation_to_paid":_rate(c.paid_customers,c.quotations),
        "paid_to_acceptance":_rate(c.accepted_deliveries,c.paid_customers),
        "acceptance_to_referral":_rate(c.referrals,c.accepted_deliveries),
        "acceptance_to_repeat":_rate(c.repeat_or_expansion,c.accepted_deliveries),
    }
    eligible={k:v for k,v in rates.items() if v is not None}
    largest_leak=min(eligible,key=eligible.get) if eligible else None
    cpql=round(c.spend/c.qualified_leads,2) if c.spend>0 and c.qualified_leads>0 else None
    return {
        "rates":rates,
        "largest_material_leak":largest_leak,
        "cost_per_qualified_lead":cpql,
        "validation_target_reached":{
            "relevant_visitors_100":c.relevant_visitors>=100,
            "qualified_leads_10":c.qualified_leads>=10,
            "quotations_3":c.quotations>=3,
            "paid_customer_1":c.paid_customers>=1,
            "case_study_1":c.case_studies>=1,
        },
        "scale_authority":False,
        "production_authority":"HUMAN_ONLY"
    }
