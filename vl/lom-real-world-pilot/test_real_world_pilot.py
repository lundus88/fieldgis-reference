import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / 'lom-continuous-improvement' / 'orchestrator.py'
spec = importlib.util.spec_from_file_location('lom44_orchestrator', ORCH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class RealWorldPilotTests(unittest.TestCase):
    def test_current_portfolio_evidence_routes_safely(self):
        fixture = json.loads((Path(__file__).parent / 'pilot_evidence.json').read_text())
        orchestrator = mod.ContinuousImprovementOrchestrator()
        results = {}
        for item in fixture['systems']:
            signal = mod.ImprovementSignal(
                signal_id=item['id'],
                target=item['target'],
                evidence_state=item['evidence_state'],
                evidence_ref='repo-evidence:' + item['signal'],
                problem=item['signal'],
                impact=0.8,
                confidence=0.9,
                risk=item['risk'],
                reversible=item['reversible'],
                production=item['production'],
            )
            results[item['id']] = orchestrator.qualify(signal).disposition
        for item in fixture['systems']:
            self.assertEqual(results[item['id']], item['expected'])

    def test_autonomous_ceiling_remains_prepare_pr(self):
        orchestrator = mod.ContinuousImprovementOrchestrator()
        self.assertEqual(
            orchestrator.finalize_validation(True, True, False, False, True),
            'PREPARE_PR',
        )
        with self.assertRaises(PermissionError):
            orchestrator.merge_protected_main()
        with self.assertRaises(PermissionError):
            orchestrator.deploy_production()

if __name__ == '__main__':
    unittest.main()
