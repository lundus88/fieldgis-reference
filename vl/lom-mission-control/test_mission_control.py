import unittest
from mission_control import MissionInput, build_snapshot

class MissionControlTests(unittest.TestCase):
    def test_missing_evidence_holds(self):
        s = build_snapshot(MissionInput("obj-1","EXECUTE","MISSING","LOW",(("EXECUTOR","READY"),)))
        self.assertEqual(s["lifecycle_state"], "HOLD")
        self.assertEqual(s["recommended_director_action"], "ACQUIRE_EVIDENCE")

    def test_high_risk_escalates(self):
        s = build_snapshot(MissionInput("obj-2","VALIDATE","COMPLETE","HIGH",(("VALIDATOR","READY"),)))
        self.assertEqual(s["lifecycle_state"], "ESCALATE")
        self.assertEqual(s["recommended_director_action"], "APPROVE_OR_REJECT")

    def test_low_risk_complete_is_observational(self):
        s = build_snapshot(MissionInput("obj-3","COMPLETE","COMPLETE","LOW",(("MEMORY_KEEPER","DONE"),)))
        self.assertEqual(s["recommended_director_action"], "NONE")

if __name__ == "__main__":
    unittest.main()
