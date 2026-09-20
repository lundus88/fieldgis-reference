#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_unapproved_partner_blocked(self):
        r=assess(PartnerSale("p1","c1","PENDING","PAID_RECONCILED",100000,1000,"v1"))
        self.assertEqual(r["commission_eligible_minor"],0)
    def test_clean_sale_computes_eligibility_only(self):
        r=assess(PartnerSale("p1","c1","APPROVED","PAID_RECONCILED",100000,1000,"v1"))
        self.assertEqual(r["commission_eligible_minor"],10000)
        self.assertFalse(r["payout_authorized"])
    def test_refund_blocks_payable_commission(self):
        r=assess(PartnerSale("p1","c1","APPROVED","PAID_RECONCILED",100000,1000,"v1",refunded_or_disputed=True))
        self.assertEqual(r["commission_eligible_minor"],0)
    def test_self_referral_review(self):
        r=assess(PartnerSale("p1","p1","APPROVED","PAID_RECONCILED",100000,1000,"v1",self_referral=True))
        self.assertIn("SELF_REFERRAL",r["risk_flags"])
    def test_no_auto_payout(self):
        self.assertFalse(automatic_payout_allowed())

if __name__=="__main__": unittest.main()
