#!/usr/bin/env python3
import unittest
from solution_catalog import *

def c(**kw):
    d=dict(component_key="quotation",version="1.0.0",state="VALIDATED",
      compatible_builders=("web-react-v1",),security_current=True,regression_current=True,
      repeatable_success_runs=3,production_projects=0,provenance_complete=True,
      licensing_clear=True,known_critical_issue=False)
    d.update(kw); return Component(**d)

class CatalogTests(unittest.TestCase):
    def test_deprecated_blocks(self):
        self.assertEqual(evaluate(c(state="DEPRECATED"),"web-react-v1")["status"],"HOLD")
    def test_builder_compatibility_required(self):
        self.assertEqual(evaluate(c(),"mobile-flutter-v1")["status"],"HOLD")
    def test_stale_security_reviews(self):
        self.assertEqual(evaluate(c(security_current=False),"web-react-v1")["status"],"REVIEW")
    def test_false_production_proven_blocked(self):
        x=c(state="PRODUCTION_PROVEN",production_projects=1,repeatable_success_runs=1)
        self.assertEqual(evaluate(x,"web-react-v1")["status"],"REVIEW")
    def test_production_proven_high_confidence(self):
        x=c(state="PRODUCTION_PROVEN",production_projects=3,repeatable_success_runs=5)
        self.assertEqual(evaluate(x,"web-react-v1")["reuse_confidence"],"HIGH")
    def test_composition_never_authorizes_build(self):
        r=compose((c(),),"web-react-v1")
        self.assertFalse(r["build_authorized"])

if __name__=="__main__": unittest.main()
