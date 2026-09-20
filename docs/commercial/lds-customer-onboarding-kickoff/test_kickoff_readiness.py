#!/usr/bin/env python3
import unittest
from kickoff_readiness import *

def ready(**kw):
    d=dict(
      approved_scope_snapshot=True,acceptance_criteria_confirmed=True,milestone_funding_evidence=True,
      customer_owner_assigned=True,ld_owner_assigned=True,communication_channel_confirmed=True,
      required_dependencies_ready=True,required_access_ready=True,environment_target_confirmed=True,
      data_handling_requirements_confirmed=True,kickoff_record_created=True,
      missing_customer_dependency=False,missing_ld_dependency=False,contradictory_evidence=False
    )
    d.update(kw); return KickoffReadiness(**d)

class KickoffTests(unittest.TestCase):
    def test_payment_alone_not_enough(self):
        r=assess(ready(approved_scope_snapshot=False))
        self.assertEqual(r["status"],"NOT_READY")
    def test_customer_dependency_routes_client_action_required(self):
        r=assess(ready(missing_customer_dependency=True))
        self.assertEqual(r["status"],"CLIENT_ACTION_REQUIRED")
        self.assertTrue(r["rebaseline_required"])
    def test_ld_dependency_routes_ld_action_required(self):
        self.assertEqual(assess(ready(missing_ld_dependency=True))["status"],"LD_ACTION_REQUIRED")
    def test_complete_readiness_still_needs_human_kickoff(self):
        r=assess(ready())
        self.assertEqual(r["status"],"READY_FOR_KICKOFF")
        self.assertFalse(r["build_allowed"])
    def test_human_kickoff_allows_build_not_production(self):
        r=kickoff("READY_FOR_KICKOFF",True)
        self.assertTrue(r["build_allowed"])
        self.assertFalse(r["production_authority"])
    def test_plaintext_secret_collection_forbidden(self):
        self.assertFalse(plaintext_secret_collection_allowed())

if __name__=="__main__": unittest.main()
