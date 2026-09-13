import unittest
from datetime import date

from match_tender import analyze_tender, evaluate_firm, load_json


class TenderEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_json("firm-registry.json")
        self.by_id = {f["id"]: f for f in self.registry["firms"]}
        self.today = date(2026, 9, 13)

    def test_lee_direct_match_when_scope_and_codes_confirmed(self):
        tender = {
            "required_ssb_codes": ["SD013"],
            "required_procurement_codes": [{"scheme": "PUKONSA", "code": "230900"}],
            "scope_confirmed": True,
        }
        result = evaluate_firm(tender, self.by_id["JURUUKUR-LEE-SURVEYS-ASSOCIATE"], self.today)
        self.assertEqual(result["decision"], "DIRECT_MATCH")

    def test_keyword_pipeline_is_candidate_not_confirmed_scope(self):
        result = analyze_tender(
            "Pipe installation works",
            "route pipeline and water pipe works",
            registry=self.registry,
            scope_confirmed=False,
            as_of=self.today,
        )
        self.assertIn("SD013", result["candidate_ssb_codes"])
        self.assertEqual(result["warning"], "KEYWORD_MATCH_IS_NOT_CONFIRMED_SCOPE")
        lee = next(x for x in result["firm_matches"] if x["firm"] == "JURUUKUR-LEE-SURVEYS-ASSOCIATE")
        self.assertEqual(lee["decision"], "CONDITIONAL_MATCH")

    def test_sejagat_restricted_new_work_is_hold(self):
        tender = {"required_ssb_codes": ["SD013"], "required_procurement_codes": [], "scope_confirmed": True}
        result = evaluate_firm(tender, self.by_id["SEJAGAT-SURVEY-CONSULTANT"], self.today)
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("NEW_WORK_AUTHORITY_NOT_FULL", result["reasons"])

    def test_loudin_stale_licence_is_hold(self):
        tender = {"required_ssb_codes": ["SD013"], "required_procurement_codes": [], "scope_confirmed": True}
        result = evaluate_firm(tender, self.by_id["JURUUKUR-LOUDIN-ASSOCIATES"], self.today)
        self.assertEqual(result["decision"], "HOLD")
        self.assertIn("SSB_LICENCE_NOT_CURRENT", result["reasons"])

    def test_missing_mandatory_procurement_code_is_conditional(self):
        tender = {
            "required_ssb_codes": ["SD013"],
            "required_procurement_codes": [{"scheme": "MOF", "code": "999999"}],
            "scope_confirmed": True,
        }
        result = evaluate_firm(tender, self.by_id["JURUUKUR-LEE-SURVEYS-ASSOCIATE"], self.today)
        self.assertEqual(result["decision"], "CONDITIONAL_MATCH")
        self.assertIn("MOF:999999", result["missing_procurement_codes"])

    def test_partial_technical_fit_is_partner_match(self):
        firm = {
            "id": "TEST-FIRM",
            "ssb_license": {"valid_until": "2026-12-31", "new_work_authority": "FULL"},
            "ssb_disciplines": ["SD012"],
            "procurement_codes": [],
        }
        tender = {"required_ssb_codes": ["SD012", "SD013"], "required_procurement_codes": [], "scope_confirmed": True}
        result = evaluate_firm(tender, firm, self.today)
        self.assertEqual(result["decision"], "PARTNER_MATCH")
        self.assertEqual(result["missing_ssb_codes"], ["SD013"])


if __name__ == "__main__":
    unittest.main()
