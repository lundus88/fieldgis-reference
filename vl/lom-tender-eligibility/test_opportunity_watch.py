import unittest

from opportunity_watch import analyze


class OpportunityWatchTests(unittest.TestCase):
    def test_direct_topographical_tender(self):
        result = analyze(
            "Topographical Survey Services",
            "Invitation for topographical survey and contour survey",
            source_type="TENDER",
            scope_confirmed=True,
        )
        self.assertEqual(result["opportunity_class"], "DIRECT_TENDER")
        self.assertIn("TOPOGRAPHICAL", result["service_categories"])
        self.assertIsNone(result["warning"])

    def test_confirmed_client_need(self):
        result = analyze(
            "Utility mapping required",
            "Developer requires underground utility mapping and GPR survey",
            source_type="DEVELOPER",
            scope_confirmed=True,
        )
        self.assertEqual(result["opportunity_class"], "CONFIRMED_CLIENT_NEED")
        self.assertIn("UTILITY_MAPPING", result["service_categories"])
        self.assertIn("SD018", result["candidate_ssb_codes"])

    def test_pipeline_project_is_potential_until_scope_confirmed(self):
        result = analyze(
            "Water pipe installation project",
            "Pipeline and water pipe works",
            source_type="PROJECT",
            scope_confirmed=False,
        )
        self.assertEqual(result["opportunity_class"], "POTENTIAL_SERVICE_NEED")
        self.assertIn("SD013", result["candidate_ssb_codes"])
        self.assertEqual(result["warning"], "KEYWORD_MATCH_IS_NOT_CONFIRMED_SCOPE")

    def test_sabah_water_bm_pipe_installation_is_inferential_only(self):
        result = analyze(
            "KERJA-KERJA PEMASANGAN PAIP JENIS MSCL",
            "Kerja pemasangan paip di Pagalungan",
            source_type="QUOTATION",
            scope_confirmed=False,
        )
        self.assertEqual(result["opportunity_class"], "POTENTIAL_SERVICE_NEED")
        self.assertEqual(result["evidence_state"], "DOWNSTREAM_INFRASTRUCTURE_SIGNAL_ONLY")
        self.assertEqual(result["warning"], "INFRASTRUCTURE_SIGNAL_IS_NOT_CONFIRMED_SURVEY_SCOPE")
        self.assertIn("pemasangan paip", result["downstream_infrastructure_signals"])
        self.assertFalse(result["scope_confirmed"])

    def test_bm_pipe_relocation_is_inferential_only(self):
        result = analyze(
            "KERJA-KERJA PENGALIHAN PAIP UNTUK PROJEK PEMBINAAN",
            "Pengalihan paip di tapak projek",
            source_type="QUOTATION",
            scope_confirmed=False,
        )
        self.assertEqual(result["opportunity_class"], "POTENTIAL_SERVICE_NEED")
        self.assertEqual(result["evidence_state"], "DOWNSTREAM_INFRASTRUCTURE_SIGNAL_ONLY")
        self.assertEqual(result["warning"], "INFRASTRUCTURE_SIGNAL_IS_NOT_CONFIRMED_SURVEY_SCOPE")
        self.assertIn("pengalihan paip", result["downstream_infrastructure_signals"])

    def test_bm_slope_repair_is_inferential_only(self):
        result = analyze(
            "Kerja pembaikan mendapan tanah dan cerun",
            "Pembaikan cerun di tapak projek",
            source_type="TENDER",
            scope_confirmed=False,
        )
        self.assertEqual(result["opportunity_class"], "POTENTIAL_SERVICE_NEED")
        self.assertEqual(result["evidence_state"], "DOWNSTREAM_INFRASTRUCTURE_SIGNAL_ONLY")
        self.assertEqual(result["warning"], "INFRASTRUCTURE_SIGNAL_IS_NOT_CONFIRMED_SURVEY_SCOPE")
        self.assertTrue(
            "pembaikan cerun" in result["downstream_infrastructure_signals"]
            or "mendapan tanah" in result["downstream_infrastructure_signals"]
        )

    def test_downstream_signal_never_becomes_direct_without_explicit_service_signal(self):
        result = analyze(
            "Pembinaan jalan baharu",
            "Kerja tanah dan pembinaan jalan",
            source_type="TENDER",
            scope_confirmed=True,
        )
        self.assertEqual(result["opportunity_class"], "POTENTIAL_SERVICE_NEED")
        self.assertEqual(result["evidence_state"], "DOWNSTREAM_INFRASTRUCTURE_SIGNAL_ONLY")

    def test_unrelated_procurement_is_not_relevant(self):
        result = analyze(
            "Office furniture supply",
            "Supply of desks, chairs and cabinets",
            source_type="TENDER",
            scope_confirmed=False,
        )
        self.assertEqual(result["opportunity_class"], "NO_RELEVANT_SIGNAL")
        self.assertEqual(result["candidate_ssb_codes"], [])
        self.assertEqual(result["service_categories"], [])
        self.assertEqual(result["downstream_infrastructure_signals"], [])

    def test_known_service_code_is_captured(self):
        result = analyze(
            "Perkhidmatan ukur tanah",
            "Kod MOF 220601 untuk kerja topografi",
            source_type="QUOTATION",
            scope_confirmed=True,
        )
        self.assertEqual(result["opportunity_class"], "DIRECT_TENDER")
        self.assertTrue(any(x["code"] == "220601" for x in result["candidate_procurement_service_codes"]))

    def test_output_contains_no_firm_ranking(self):
        result = analyze("GIS mapping", "geospatial mapping services", source_type="CLIENT", scope_confirmed=True)
        self.assertNotIn("firm_matches", result)
        self.assertNotIn("firm", result)
        self.assertNotIn("partner", result)


if __name__ == "__main__":
    unittest.main()
