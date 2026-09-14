import unittest
from decision import DecisionRequest, classify, build_decision_package

BASE='a'*40
CAND='b'*40
EVID='c'*40
MAN='d'*64


def req(**kw):
    data=dict(
        workload_id='ebkl', base_sha=BASE, candidate_sha=CAND, evidence_sha=EVID,
        manifest_sha256=MAN, source_reference='ci://ebkl/123', promotion_status='PREPARE_PR',
        rollback_ready=True, residual_risks=(), target_action='NON_PRODUCTION_REVERSIBLE_ACTION',
        risk='LOW', production=False,
    )
    data.update(kw)
    return DecisionRequest(**data)


class DecisionTests(unittest.TestCase):
    def test_ready(self): self.assertEqual(classify(req())['status'],'READY_FOR_HUMAN_DECISION')
    def test_missing_workload(self): self.assertEqual(classify(req(workload_id=''))['status'],'HOLD')
    def test_bad_base_sha(self): self.assertEqual(classify(req(base_sha='x'))['status'],'HOLD')
    def test_bad_candidate_sha(self): self.assertEqual(classify(req(candidate_sha='x'))['status'],'HOLD')
    def test_bad_evidence_sha(self): self.assertEqual(classify(req(evidence_sha='x'))['status'],'HOLD')
    def test_same_sha(self): self.assertEqual(classify(req(candidate_sha=BASE))['status'],'HOLD')
    def test_bad_manifest(self): self.assertEqual(classify(req(manifest_sha256='x'))['status'],'HOLD')
    def test_missing_source(self): self.assertEqual(classify(req(source_reference=''))['status'],'HOLD')
    def test_promotion_not_ready(self): self.assertEqual(classify(req(promotion_status='HOLD'))['status'],'HOLD')
    def test_rollback_not_ready(self): self.assertEqual(classify(req(rollback_ready=False))['status'],'HOLD')
    def test_unknown_risk(self): self.assertEqual(classify(req(risk='EXTREME'))['status'],'HOLD')
    def test_high_risk(self): self.assertEqual(classify(req(risk='HIGH'))['status'],'HUMAN_REVIEW')
    def test_production(self): self.assertEqual(classify(req(production=True))['status'],'HUMAN_REVIEW')
    def test_human_only_target(self): self.assertEqual(classify(req(target_action='PROTECTED_MAIN_MERGE'))['status'],'HUMAN_REVIEW')
    def test_residual_risks(self): self.assertEqual(build_decision_package(req(residual_risks=('known limitation',)))['recommended_disposition'],'APPROVE_ONLY_IF_RESIDUAL_RISKS_ACCEPTED')
    def test_no_auto_authority(self):
        p=build_decision_package(req())
        self.assertTrue(p['human_decision_required']); self.assertEqual(p['auto_approve'],'DISABLED'); self.assertEqual(p['auto_merge'],'DISABLED'); self.assertEqual(p['production_deploy'],'DISABLED')

if __name__ == '__main__': unittest.main()
