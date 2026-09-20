#!/usr/bin/env python3
import unittest
from anti_bottleneck import *

class AntiBottleneckTests(unittest.TestCase):
    def test_wait_state_requires_owner_and_release_condition(self):
        r=wait_guard(WaitState("WAITING_CUSTOMER",10,60,240,False,True,30))
        self.assertEqual(r["reason"],"UNOWNED_OR_UNRELEASABLE_WAIT")

    def test_soft_timeout_notifies_but_does_not_autoapprove(self):
        r=wait_guard(WaitState("HUMAN_APPROVAL_REQUIRED",70,60,240,True,True,15,True))
        self.assertEqual(r["status"],"AUTO_NOTIFY")
        self.assertFalse(r["auto_approval_allowed"])

    def test_hard_timeout_escalates_not_bypasses(self):
        r=wait_guard(WaitState("HUMAN_APPROVAL_REQUIRED",241,60,240,True,True,15,True))
        self.assertEqual(r["status"],"HUMAN_GATE")
        self.assertFalse(r["auto_approval_allowed"])

    def test_queue_aging_prevents_starvation(self):
        r=queue_rank([
          QueueItem("new-high",10,0),
          QueueItem("old-low",2,600)
        ],60)
        self.assertEqual(r["ranked"][0]["project_id"],"old-low")

    def test_certified_fallback_can_be_selected_nonproduction(self):
        r=provider_fallback(ProviderState("primary",False,"backup",True,True,False))
        self.assertEqual(r["reason"],"CERTIFIED_FALLBACK_SELECTED")
        self.assertFalse(r["production_authority"])

    def test_no_provider_fallback_queues_safely(self):
        r=provider_fallback(ProviderState("primary",False))
        self.assertEqual(r["reason"],"PROVIDER_OUTAGE_QUEUED")

    def test_project_without_path_is_blocked(self):
        r=progress_guard(ProgressHeartbeat("P1",5,30,False,False))
        self.assertEqual(r["reason"],"PROJECT_STUCK_WITHOUT_PATH")

    def test_state_loop_is_detected(self):
        r=progress_guard(ProgressHeartbeat("P1",5,30,True,False,3,3))
        self.assertEqual(r["reason"],"STATE_LOOP_DETECTED")

    def test_approval_backup_reassignment_preserves_authority(self):
        r=approval_guard(ApprovalGate("quote",121,30,120,True,True,True))
        self.assertEqual(r["reason"],"APPROVAL_ESCALATED_TO_BACKUP")
        self.assertFalse(r["auto_approval_allowed"])

if __name__=="__main__":
    unittest.main()
