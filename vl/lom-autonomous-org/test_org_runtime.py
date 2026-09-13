import unittest
from org_runtime import route, learn

class OrgRuntimeTests(unittest.TestCase):
    def test_human_only_escalates(self):
        self.assertEqual(route("PRODUCTION_RELEASE","COMPLETE","LOW",True,False)["decision"], "ESCALATE")

    def test_missing_evidence_holds(self):
        self.assertEqual(route("RUN_TEST","MISSING","LOW",True,False)["decision"], "HOLD")

    def test_low_risk_reversible_delegates(self):
        self.assertEqual(route("RUN_TEST","COMPLETE","LOW",True,False)["decision"], "DELEGATE")

    def test_unknown_action_holds(self):
        result = route("UNKNOWN_ACTION","COMPLETE","LOW",True,False)
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["reason"], "UNKNOWN_OR_UNDELEGATED_AUTHORITY")

    def test_learning_is_propose_only(self):
        self.assertEqual(learn(True,"adjust threshold")["policy_effect"], "PROPOSE_ONLY")

if __name__ == "__main__":
    unittest.main()
