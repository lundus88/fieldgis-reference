#!/usr/bin/env python3
import unittest
from delivery_benchmark import *

def r(cls="BUSINESS_SYSTEM",d=10,current=True):
    return DeliveryRecord(cls,2,d,500000,5,4,1,2,current)

class DeliveryBenchmarkTests(unittest.TestCase):
    def test_small_sample_insufficient(self):
        self.assertEqual(summarize((r(),r()),"BUSINESS_SYSTEM")["status"],"INSUFFICIENT_EVIDENCE")
    def test_stale_records_review(self):
        recs=(r(),r(),r(current=False))
        self.assertEqual(summarize(recs,"BUSINESS_SYSTEM")["status"],"REVIEW")
    def test_medium_sample_ready(self):
        recs=(r(d=8),r(d=10),r(d=12))
        out=summarize(recs,"BUSINESS_SYSTEM")
        self.assertEqual(out["status"],"BENCHMARK_READY")
        self.assertEqual(out["confidence"],"MEDIUM")
    def test_spread_exposed(self):
        recs=(r(d=8),r(d=10),r(d=12))
        out=summarize(recs,"BUSINESS_SYSTEM")
        self.assertEqual(out["delivery_cycle_days"]["min"],8)
        self.assertEqual(out["delivery_cycle_days"]["max"],12)
    def test_never_auto_eta_or_reprice(self):
        recs=tuple(r(d=10+i) for i in range(8))
        out=summarize(recs,"BUSINESS_SYSTEM")
        self.assertFalse(out["auto_customer_eta"])
        self.assertFalse(out["auto_reprice"])
    def test_approved_commitment_immutable_here(self):
        self.assertFalse(can_overwrite_approved_commitment())

if __name__=="__main__": unittest.main()
