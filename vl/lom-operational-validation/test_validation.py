import unittest
from datetime import date

from validate_pipeline import validate


class OperationalValidationTests(unittest.TestCase):
    def test_active_missing_conversion_is_hold(self):
        live = [{"id": "JANS-PIPE-PAGALUNGAN-2026", "status": "HOLD", "closing_date": "2026-09-21"}]
        findings = validate(live, [], today=date(2026, 9, 13))
        self.assertEqual(findings[0]["type"], "ACTIVE_SIGNAL_MISSING_CONVERSION")
        self.assertEqual(findings[0]["severity"], "HOLD")

    def test_historical_watchlist_missing_conversion_is_not_failure(self):
        live = [{"id": "HISTORICAL-SURVEY", "status": "WATCHLIST", "closing_date": "2026-03-24"}]
        self.assertEqual(validate(live, [], today=date(2026, 9, 13)), [])

    def test_governance_widening_is_blocked(self):
        live = [{"id": "A", "status": "HOLD", "closing_date": "2026-10-05"}]
        conversion = [{"id": "A", "status": "CONTINUE", "active_until": "2026-10-05"}]
        findings = validate(live, conversion, today=date(2026, 9, 13))
        self.assertTrue(any(x["type"] == "GOVERNANCE_STATE_WIDENED" for x in findings))

    def test_date_mismatch_requires_review(self):
        live = [{"id": "A", "status": "HOLD", "closing_date": "2026-10-05"}]
        conversion = [{"id": "A", "status": "HOLD", "active_until": "2026-10-06"}]
        findings = validate(live, conversion, today=date(2026, 9, 13))
        self.assertTrue(any(x["type"] == "DATE_MISMATCH" and x["severity"] == "REVIEW" for x in findings))

    def test_invalid_date_fails_closed(self):
        live = [{"id": "A", "status": "HOLD", "closing_date": "not-a-date"}]
        findings = validate(live, [], today=date(2026, 9, 13))
        self.assertEqual(findings[0]["type"], "INVALID_DATE")
        self.assertEqual(findings[0]["severity"], "HOLD")


if __name__ == "__main__":
    unittest.main()
