#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_plan_required(self):
        self.assertEqual(resolve(Subscription("o1",False,"ACTIVE",("support",),True))["status"],"REVIEW")
    def test_active_entitlements(self):
        r=resolve(Subscription("o1",True,"ACTIVE",("support","hosting"),True))
        self.assertEqual(r["entitlements"],["support","hosting"])
        self.assertFalse(r["auto_charge"])
    def test_past_due_is_review_not_destructive(self):
        r=resolve(Subscription("o1",True,"PAST_DUE",("support",),False))
        self.assertEqual(r["renewal_state"],"PAYMENT_REVIEW")
        self.assertFalse(r["irreversible_action_authorized"])
    def test_no_auto_charge(self):
        self.assertFalse(auto_charge_allowed())

if __name__=="__main__": unittest.main()
