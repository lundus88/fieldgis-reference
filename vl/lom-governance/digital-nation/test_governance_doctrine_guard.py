import unittest
from governance_doctrine_guard import load_docs, validate_governance_docs

class GovernanceDoctrineTests(unittest.TestCase):
    def test_current_governance_docs_are_consistent(self):
        self.assertEqual(validate_governance_docs(load_docs()),[])

    def test_election_power_phrase_is_blocked(self):
        docs=load_docs()
        docs["world"] += "\nPlatform governance voting where appropriate\n"
        errors=validate_governance_docs(docs)
        self.assertTrue(any(e.startswith("FORBIDDEN_GOVERNANCE_PHRASE:") for e in errors))

    def test_founder_led_model_cannot_silently_disappear(self):
        docs=load_docs()
        docs["charter"]=docs["charter"].replace("Founder-Led Constitutional Platform","Different model")
        self.assertIn("CHARTER_FOUNDER_LED_MODEL_MISSING",validate_governance_docs(docs))

    def test_best_of_world_principle_is_locked(self):
        docs=load_docs()
        docs["charter"]=docs["charter"].replace("BEST-OF-WORLD ARCHITECTURE","REMOVED PRINCIPLE")
        self.assertIn("BEST_OF_WORLD_ARCHITECTURE_MISSING",validate_governance_docs(docs))

if __name__=="__main__":
    unittest.main()
