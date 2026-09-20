#!/usr/bin/env python3
import unittest
from customer_success import *

class CustomerSuccessTests(unittest.TestCase):
    def test_no_complaint_not_enough(self):
        e=SuccessEvidence(True,True,False)
        self.assertEqual(evaluate(e)["status"],"SUCCESS_CHECK_PENDING")
    def test_unresolved_issue_blocks_referral(self):
        e=SuccessEvidence(True,True,True,unresolved_issue=True,referral_permission=True)
        self.assertFalse(evaluate(e)["referral_allowed"])
    def test_testimonial_needs_permission(self):
        e=SuccessEvidence(True,True,True,testimonial_permission=False)
        self.assertEqual(testimonial_action(e)["decision"],"HOLD")
    def test_referral_needs_permission(self):
        e=SuccessEvidence(True,True,True,referral_permission=False)
        self.assertEqual(referral_action(e)["decision"],"HOLD")
    def test_testimonial_never_auto_publish(self):
        e=SuccessEvidence(True,True,True,testimonial_permission=True)
        self.assertFalse(testimonial_action(e)["auto_publish"])
    def test_referral_never_auto_contact(self):
        e=SuccessEvidence(True,True,True,referral_permission=True)
        self.assertFalse(referral_action(e)["auto_contact_referral"])

if __name__=="__main__": unittest.main()
