#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_unsupported_market_reviews(self):
        r=resolve(LocaleRequest("XX","en-XX","v1","p1",True))
        self.assertEqual(r["status"],"FALLBACK_REVIEW")
    def test_unsupported_locale_reviews(self):
        r=resolve(LocaleRequest("MY","fr-FR","v1","p1",True))
        self.assertEqual(r["status"],"FALLBACK_REVIEW")
    def test_supported_locale_resolves_display_only(self):
        r=resolve(LocaleRequest("MY","ms-MY","v1","p1",True))
        self.assertEqual(r["resolved_currency_display"],"MYR")
        self.assertEqual(r["status"],"READY_FOR_HUMAN_MARKET_REVIEW")
        self.assertFalse(r["production_activation_authorized"])
    def test_unreviewed_translation_blocks_ready(self):
        r=resolve(LocaleRequest("SG","en-SG","v1","p1",False))
        self.assertIn("TRANSLATION_REVIEW_REQUIRED",r["risk_flags"])
    def test_no_auto_legal_translation(self):
        self.assertFalse(automatic_legal_translation_allowed())

if __name__=="__main__": unittest.main()
