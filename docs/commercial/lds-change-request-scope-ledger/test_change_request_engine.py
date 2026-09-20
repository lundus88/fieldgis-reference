#!/usr/bin/env python3
import unittest
from change_request_engine import *

def cr(**kw):
    d=dict(
        material_change=True,within_original_scope=False,defect_or_rework=False,
        cost_impact_known=True,time_impact_known=True,customer_approved=False,
        human_commercial_approved=False,evidence_complete=True,base_scope_version=1
    )
    d.update(kw)
    return ChangeRequest(**d)

class ChangeRequestTests(unittest.TestCase):
    def test_original_scope_not_billed_as_change(self):
        r=assess(cr(within_original_scope=True))
        self.assertFalse(r["billable_change"])
    def test_defect_remediation_not_billed_as_change(self):
        r=assess(cr(defect_or_rework=True))
        self.assertFalse(r["billable_change"])
    def test_unknown_impact_blocks(self):
        self.assertEqual(assess(cr(cost_impact_known=False))["state"],"IMPACT_REVIEW")
    def test_customer_approval_required(self):
        self.assertEqual(assess(cr(customer_approved=False))["state"],"CUSTOMER_DECISION")
    def test_human_commercial_approval_required(self):
        self.assertEqual(assess(cr(customer_approved=True))["state"],"APPROVAL_PENDING")
    def test_approved_change_creates_new_scope_version(self):
        r=assess(cr(customer_approved=True,human_commercial_approved=True,base_scope_version=3))
        self.assertEqual(r["new_scope_version"],4)
        self.assertTrue(r["preserve_prior_scope"])
    def test_unapproved_change_cannot_apply(self):
        self.assertEqual(apply_change("REQUESTED",2)["decision"],"HOLD")
    def test_quote_cannot_be_silently_modified(self):
        self.assertFalse(can_silently_modify_quote())

if __name__=="__main__":
    unittest.main()
