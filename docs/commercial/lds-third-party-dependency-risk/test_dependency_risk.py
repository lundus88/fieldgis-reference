#!/usr/bin/env python3
import unittest
from dependency_risk import *

def dep(**kw):
    d=dict(provider_key="supabase",project_ids=("p1",),criticality="HIGH",
           fallback_available=True,fallback_verified=True,owner_known=True,
           evidence_current=True,provider_healthy=True)
    d.update(kw); return Dependency(**d)

class DependencyRiskTests(unittest.TestCase):
    def test_unknown_projects_reviews(self):
        self.assertEqual(assess(dep(project_ids=()))["status"],"REVIEW")
    def test_stale_evidence_reviews(self):
        self.assertEqual(assess(dep(evidence_current=False))["status"],"REVIEW")
    def test_high_impact_outage_without_fallback_holds(self):
        r=assess(dep(provider_healthy=False,fallback_verified=False))
        self.assertEqual(r["status"],"HOLD")
        self.assertFalse(r["auto_failover"])
    def test_outage_never_auto_contacts_customer(self):
        r=assess(dep(provider_healthy=False))
        self.assertFalse(r["auto_customer_contact"])
    def test_fallback_must_be_verified(self):
        self.assertEqual(assess(dep(fallback_available=True,fallback_verified=False))["status"],"REVIEW")
    def test_no_auto_switch(self):
        self.assertFalse(can_auto_switch_provider())

if __name__=="__main__": unittest.main()
