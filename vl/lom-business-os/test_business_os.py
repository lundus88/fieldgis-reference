import unittest
from business_os import BusinessEvidence, recommend

class BusinessOSTests(unittest.TestCase):
    def test_missing_evidence_holds(self):
        r = recommend(BusinessEvidence("p1","MISSING","HIGH","LOW","HIGH","HIGH"))
        self.assertEqual(r["recommendation"], "HOLD")

    def test_high_risk_requires_review(self):
        r = recommend(BusinessEvidence("p2","COMPLETE","HIGH","HIGH","HIGH","HIGH"))
        self.assertEqual(r["recommendation"], "REVIEW")

    def test_evidence_supported_priority(self):
        r = recommend(BusinessEvidence("p3","COMPLETE","HIGH","LOW","HIGH","HIGH"))
        self.assertEqual(r["recommendation"], "PRIORITISE")
        self.assertEqual(r["authority"], "ADVISORY_ONLY")

if __name__ == "__main__":
    unittest.main()
