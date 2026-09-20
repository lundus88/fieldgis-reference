#!/usr/bin/env python3
import unittest
from knowledge_center import *

def a(**kw):
    d=dict(article_type="HOW_TO",version_matches=True,evidence_verified=True,
           evidence_current=True,customer_authorized=True,
           contains_security_bypass=False,contains_hidden_known_limit=False,
           requires_human_support=False)
    d.update(kw); return Article(**d)

class KnowledgeCenterTests(unittest.TestCase):
    def test_unauthorized_denied(self):
        self.assertEqual(assess(a(customer_authorized=False))["status"],"DENY")
    def test_version_mismatch_reviews(self):
        self.assertEqual(assess(a(version_matches=False))["status"],"REVIEW")
    def test_stale_article_reviews(self):
        self.assertEqual(assess(a(evidence_current=False))["status"],"REVIEW")
    def test_security_bypass_holds(self):
        self.assertEqual(assess(a(contains_security_bypass=True))["status"],"HOLD")
    def test_known_limit_cannot_be_hidden(self):
        self.assertEqual(assess(a(contains_hidden_known_limit=True))["status"],"HOLD")
    def test_human_support_route_preserved(self):
        r=assess(a(requires_human_support=True))
        self.assertTrue(r["support_route_required"])
        self.assertFalse(r["self_service_allowed"])
    def test_security_escalation_not_replaced(self):
        self.assertFalse(may_replace_security_escalation())

if __name__=="__main__": unittest.main()
