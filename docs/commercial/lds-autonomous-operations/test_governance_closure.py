#!/usr/bin/env python3
import unittest
from governance_closure import *

class GovernanceClosureTests(unittest.TestCase):
    def test_unknown_policy_fails_closed(self):
        r=evaluate_policy(PolicyDecision("", "x", False, "NON_PRODUCTION", "LOW", True))
        self.assertEqual(r["status"],"HUMAN_GATE")

    def test_jit_access_is_bounded(self):
        r=broker_access(AccessLeaseRequest("preview","T-1",True,15,30))
        self.assertTrue(r["lease_issued"])
        self.assertTrue(r["revocation_required"])

    def test_production_admin_never_auto_leased(self):
        r=broker_access(AccessLeaseRequest("admin","T-2",True,5,30,production_admin=True))
        self.assertEqual(r["status"],"HUMAN_GATE")

    def test_provenance_requires_attestation(self):
        r=provenance_gate(ProvenanceEvidence(True,True,True,True,True,False,True))
        self.assertFalse(r["release_claim_allowed"])

    def test_chaos_is_nonproduction_only(self):
        r=chaos_verify(ChaosScenario("PRODUCTION",False,False,False,"provider_outage",True,True))
        self.assertEqual(r["status"],"HUMAN_GATE")

    def test_portability_composes_existing_package(self):
        r=portability_gate(PortabilityEvidence(True,True,True,True,True,True))
        self.assertEqual(r["source_of_truth"],"lds-handover-exit-package")

    def test_business_health_can_constrain_not_reprice(self):
        r=business_health_governor(BusinessHealth(True,"HEALTHY","OVERLOADED","HEALTHY","NORMAL","LOW"))
        self.assertEqual(r["admission"],"CONSTRAIN_NEW_WORK")
        self.assertFalse(r["pricing_mutation_allowed"])

if __name__=="__main__":
    unittest.main()
