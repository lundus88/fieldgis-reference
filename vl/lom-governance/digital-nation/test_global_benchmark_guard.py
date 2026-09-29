import unittest
from pathlib import Path
from global_benchmark_guard import load_json, validate_registry, validate_hypotheses, preview_decision

ROOT=Path(__file__).resolve().parent
REG=ROOT/"global-nation-benchmark-v1.json"
HYP=ROOT/"benchmark-hypotheses-v1.json"

class GlobalBenchmarkGuardTests(unittest.TestCase):
    def test_framework_is_research_ready(self):
        r=load_json(REG)
        h=load_json(HYP)
        self.assertEqual(validate_registry(r),[])
        self.assertEqual(validate_hypotheses(h),[])
        out=preview_decision(r,h)
        self.assertEqual(out["decision"],"ALLOW_RESEARCH")
        self.assertFalse(out["country_ranking_authority"])
        self.assertFalse(out["political_winner_authority"])
        self.assertFalse(out["production_authority"])

    def test_country_pool_range_is_enforced(self):
        r=load_json(REG)
        r["country_pool"]=r["country_pool"][:10]
        self.assertIn("COUNTRY_POOL_MUST_BE_20_TO_30",validate_registry(r))

    def test_overall_ranking_prohibition_is_mandatory(self):
        r=load_json(REG)
        r["forbidden_outputs"].remove("country_rank")
        self.assertIn("MISSING_FORBIDDEN_OUTPUT:country_rank",validate_registry(r))

    def test_user_nominated_hypothesis_cannot_become_fact_without_review(self):
        h=load_json(HYP)
        h["hypotheses"][0]["evidence_status"]="VERIFIED"
        self.assertTrue(any(e.startswith("HYPOTHESIS_PREMATURELY_PROMOTED:") for e in validate_hypotheses(h)))

if __name__=="__main__":
    unittest.main()
