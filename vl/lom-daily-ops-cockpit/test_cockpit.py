import unittest
from cockpit import DailyOpsCockpit, PortfolioSignal

class DailyOpsCockpitTests(unittest.TestCase):
    def setUp(self):
        self.c = DailyOpsCockpit()

    def sig(self, **kw):
        base = dict(project_id='vl', health='HEALTHY', evidence_state='READY', evidence_ref='commit:1', target='OBSERVABILITY', risk='LOW', reversible=True, production=False)
        base.update(kw)
        return PortfolioSignal(**base)

    def test_missing_evidence_holds(self):
        d = self.c.classify(self.sig(evidence_state='STALE'))
        self.assertEqual(d.action_class,'HOLD')

    def test_missing_evidence_ref_holds(self):
        d = self.c.classify(self.sig(evidence_ref=''))
        self.assertEqual(d.action_class,'HOLD')

    def test_physical_verification_holds(self):
        d = self.c.classify(self.sig(project_id='sabahlot', physical_verification_required=True, physical_verification_complete=False))
        self.assertEqual(d.action_class,'HOLD')

    def test_production_requires_human(self):
        d = self.c.classify(self.sig(project_id='ebkl', production=True))
        self.assertEqual(d.action_class,'HUMAN_REVIEW')

    def test_human_only_target_requires_human(self):
        d = self.c.classify(self.sig(target='PROTECTED_MAIN_MERGE'))
        self.assertEqual(d.action_class,'HUMAN_REVIEW')

    def test_high_risk_requires_human(self):
        d = self.c.classify(self.sig(risk='HIGH'))
        self.assertEqual(d.action_class,'HUMAN_REVIEW')

    def test_irreversible_holds(self):
        d = self.c.classify(self.sig(reversible=False))
        self.assertEqual(d.action_class,'HOLD')

    def test_blocked_nonprod_can_be_prepared(self):
        d = self.c.classify(self.sig(project_id='ll', health='BLOCKED'))
        self.assertEqual(d.action_class,'AUTO_PREPARE')

    def test_review_nonprod_can_be_prepared(self):
        d = self.c.classify(self.sig(project_id='ll', health='REVIEW'))
        self.assertEqual(d.action_class,'AUTO_PREPARE')

    def test_healthy_monitors(self):
        d = self.c.classify(self.sig())
        self.assertEqual(d.action_class,'MONITOR')

    def test_priority_sort(self):
        rows = self.c.build([
            self.sig(project_id='healthy'),
            self.sig(project_id='prod', production=True),
            self.sig(project_id='phone', physical_verification_required=True, physical_verification_complete=False),
        ])
        self.assertEqual([x.project_id for x in rows], ['phone','prod','healthy'])

    def test_autonomous_ceiling(self):
        self.assertEqual(self.c.autonomous_ceiling(),'PREPARE_PR')

    def test_self_merge_forbidden(self):
        with self.assertRaisesRegex(PermissionError,'HUMAN_APPROVAL_REQUIRED'):
            self.c.merge_protected_main()

    def test_self_deploy_forbidden(self):
        with self.assertRaisesRegex(PermissionError,'HUMAN_APPROVAL_REQUIRED'):
            self.c.deploy_production()

if __name__ == '__main__':
    unittest.main()
