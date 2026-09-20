#!/usr/bin/env python3
import unittest
from proof_engine import ProofEvidence,publication_state

class ProofEngineTests(unittest.TestCase):
    def test_verified_permitted_proof_is_publishable(self):
        r=publication_state(ProofEvidence(True,True,True,True,True))
        self.assertEqual(r["state"],"PUBLISHABLE")

    def test_missing_permission_is_internal(self):
        r=publication_state(ProofEvidence(True,True,True,False,True))
        self.assertEqual(r["state"],"INTERNAL_ONLY")

    def test_fabricated_claim_holds(self):
        r=publication_state(ProofEvidence(True,True,False,False,True,True))
        self.assertEqual(r["state"],"HOLD")

if __name__=="__main__":
    unittest.main()
