#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_policy_required(self):
        r=assess(DataDecision("","CONFIDENTIAL",10,30))
        self.assertEqual(r["status"],"REVIEW")
    def test_legal_hold_blocks_deletion(self):
        r=assess(DataDecision("v1","CONFIDENTIAL",100,30,True,True))
        self.assertEqual(r["deletion_status"],"BLOCKED_BY_LEGAL_HOLD")
    def test_export_requires_authorization(self):
        r=assess(DataDecision("v1","CONFIDENTIAL",10,30,export_request=True,identity_authorized=False))
        self.assertIn("EXPORT_AUTHORIZATION_MISSING",r["risk_flags"])
    def test_no_auto_delete(self):
        self.assertFalse(automatic_destructive_deletion_allowed())

if __name__=="__main__": unittest.main()
