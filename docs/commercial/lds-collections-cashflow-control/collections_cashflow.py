#!/usr/bin/env python3
from dataclasses import dataclass
from datetime import date
from typing import Dict

@dataclass(frozen=True)
class Receivable:
    amount_minor:int
    paid_minor:int
    due_date:date
    today:date
    payment_reconciled:bool
    disputed:bool=False
    cancelled:bool=False
    refunded:bool=False

def classify(r:Receivable)->Dict:
    if r.cancelled:
        return {"state":"CANCELLED","outstanding_minor":0}
    if r.refunded:
        return {"state":"REFUNDED","outstanding_minor":0}
    if r.disputed:
        return {"state":"DISPUTED","outstanding_minor":max(0,r.amount_minor-r.paid_minor),"auto_reminder":False}
    if r.payment_reconciled and r.paid_minor>=r.amount_minor:
        return {"state":"PAID","outstanding_minor":0}
    outstanding=max(0,r.amount_minor-r.paid_minor)
    days=(r.due_date-r.today).days
    if days>7:
        state="NOT_DUE"
    elif days>0:
        state="DUE_SOON"
    elif days==0:
        state="DUE"
    else:
        state="OVERDUE"
    return {"state":state,"outstanding_minor":outstanding,"auto_reminder":False}

def reminder_decision(state:str,cadence_approved:bool,channel_approved:bool,human_override:bool=False)->Dict:
    if state=="DISPUTED":
        return {"decision":"HOLD","reason":"DISPUTE_REQUIRES_HUMAN_REVIEW"}
    if state not in {"DUE_SOON","DUE","OVERDUE"}:
        return {"decision":"NO_REMINDER"}
    if not cadence_approved or not channel_approved:
        return {"decision":"HOLD","reason":"REMINDER_POLICY_NOT_APPROVED"}
    return {"decision":"PREPARE_REMINDER","send_authorized":False,"requires_human_or_approved_automation":True}

def can_mutate_invoice_amount()->bool:
    return False
