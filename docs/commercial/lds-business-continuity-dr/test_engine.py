#!/usr/bin/env python3
import unittest
from engine import *

class Tests(unittest.TestCase):
    def test_stale_backup_flags_rpo(self):
        r=assess(RecoveryEvidence(60,240,120,10,True,True))
        self.assertIn("RPO_BREACH_OR_BACKUP_STALE",r["risk_flags"])
    def test_integrity_uncertainty_blocks_failover(self):
        r=assess(RecoveryEvidence(60,240,30,10,False,True,True))
        self.assertEqual(r["fallback_recommendation"],"NO_AUTOMATIC_FAILOVER")
        self.assertFalse(r["production_failover_authorized"])
    def test_recovery_evidence_ready_still_human_gated(self):
        r=assess(RecoveryEvidence(60,240,30,30,True,True))
        self.assertEqual(r["status"],"RECOVERY_EVIDENCE_READY")
        self.assertFalse(r["restore_authorized"])
    def test_restore_test_freshness(self):
        r=assess(RecoveryEvidence(60,240,30,120,True,True))
        self.assertIn("RESTORE_TEST_STALE",r["risk_flags"])
    def test_no_auto_restore(self):
        self.assertFalse(automatic_restore_allowed())

if __name__=="__main__": unittest.main()
