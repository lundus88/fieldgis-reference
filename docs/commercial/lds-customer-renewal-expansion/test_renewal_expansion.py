#!/usr/bin/env python3
import unittest
from renewal_expansion import *

class RenewalExpansionTests(unittest.TestCase):
    def test_unresolved_issue_blocks_upsell(self):
        e=CustomerGrowthEvidence(False,True,True,True,True,True,True)
        r=evaluate(e)
        self.assertEqual(r["decision"],"RETENTION_FOLLOW_UP")
        self.assertFalse(r["upsell_allowed"])
    def test_expiring_plan_never_auto_renews(self):
        e=CustomerGrowthEvidence(True,True,False,True,False,True,True)
        r=evaluate(e)
        self.assertEqual(r["decision"],"RENEWAL_REVIEW")
        self.assertFalse(r["auto_renew"])
    def test_expansion_needs_success_evidence(self):
        e=CustomerGrowthEvidence(False,False,False,True,True,True,True)
        self.assertEqual(evaluate(e)["decision"],"RETENTION_FOLLOW_UP")
    def test_capacity_constrained_expansion_stays_review(self):
        e=CustomerGrowthEvidence(False,True,False,True,True,True,False)
        r=evaluate(e)
        self.assertEqual(r["decision"],"EXPANSION_REVIEW")
        self.assertFalse(r["binding_offer_allowed"])
    def test_healthy_expansion_still_not_binding(self):
        e=CustomerGrowthEvidence(False,True,False,True,True,True,True)
        r=evaluate(e)
        self.assertEqual(r["decision"],"EXPANSION_REVIEW")
        self.assertFalse(r["binding_offer_allowed"])
    def test_no_auto_actions(self):
        self.assertFalse(can_auto_renew())
        self.assertFalse(can_auto_contact())

if __name__=="__main__": unittest.main()
