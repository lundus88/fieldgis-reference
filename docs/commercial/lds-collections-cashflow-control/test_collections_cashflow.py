#!/usr/bin/env python3
import unittest
from datetime import date,timedelta
from collections_cashflow import *

class CashflowTests(unittest.TestCase):
    def test_paid_requires_reconciliation(self):
        r=Receivable(1000,1000,date.today(),date.today(),False)
        self.assertNotEqual(classify(r)["state"],"PAID")
    def test_dispute_pauses_reminder(self):
        r=Receivable(1000,0,date.today()-timedelta(days=10),date.today(),False,disputed=True)
        x=classify(r)
        self.assertEqual(x["state"],"DISPUTED")
        self.assertFalse(x["auto_reminder"])
    def test_overdue_not_fraud(self):
        r=Receivable(1000,0,date.today()-timedelta(days=1),date.today(),False)
        self.assertEqual(classify(r)["state"],"OVERDUE")
    def test_reminder_needs_policy(self):
        self.assertEqual(reminder_decision("OVERDUE",False,True)["decision"],"HOLD")
    def test_reminder_never_directly_sends(self):
        r=reminder_decision("OVERDUE",True,True)
        self.assertFalse(r["send_authorized"])
    def test_invoice_amount_immutable_here(self):
        self.assertFalse(can_mutate_invoice_amount())

if __name__=="__main__": unittest.main()
