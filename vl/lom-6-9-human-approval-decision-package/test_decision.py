import unittest
from decision import DecisionRequest, classify, build_decision_package, _canonical_manifest_digest

BASE='a'*40
CAND='b'*40
EVID='c'*40
VAL='1'*64
ROLL='2'*64


def promotion_manifest(**kw):
    data={
        'schema':'lom.pr-evidence-promotion/2',
        'workload_id':'ebkl',
        'base_sha':BASE,
        'candidate_sha':CAND,
        'evidence_sha':EVID,
        'source_reference':'ci://ebkl/123',
        'validation_status':'PREPARE_PR',
        'validation_package_sha256':VAL,
        'rollback_plan_sha256':ROLL,
        'target_action':'NON_PRODUCTION_REVERSIBLE_ACTION',
        'production':False,
        'risk':'LOW',
        'autonomous_ceiling':'PREPARE_PR',
        'production_authority':'HUMAN_ONLY',
        'auto_merge':'DISABLED',
        'production_execution':'DISABLED',
    }
    data.update(kw)
    data['manifest_sha256']=_canonical_manifest_digest(data)
    return data


def req(**kw):
    manifest = kw.pop('promotion_manifest', promotion_manifest())
    manifest_sha = kw.pop('manifest_sha256', manifest.get('manifest_sha256', _canonical_manifest_digest(manifest)))
    data=dict(
        workload_id='ebkl', base_sha=BASE, candidate_sha=CAND, evidence_sha=EVID,
        manifest_sha256=manifest_sha, promotion_manifest=manifest,
        source_reference='ci://ebkl/123', promotion_status='PREPARE_PR',
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
    def test_bad_manifest_digest_format(self): self.assertEqual(classify(req(manifest_sha256='x'))['reason'],'MANIFEST_DIGEST_REQUIRED')
    def test_missing_source(self): self.assertEqual(classify(req(source_reference=''))['status'],'HOLD')
    def test_promotion_not_ready(self): self.assertEqual(classify(req(promotion_status='HOLD'))['status'],'HOLD')
    def test_rollback_not_ready(self): self.assertEqual(classify(req(rollback_ready=False))['status'],'HOLD')
    def test_unknown_risk(self): self.assertEqual(classify(req(risk='EXTREME'))['status'],'HOLD')
    def test_high_risk(self): self.assertEqual(classify(req(risk='HIGH', promotion_manifest=promotion_manifest(risk='HIGH')))['status'],'HUMAN_REVIEW')
    def test_production(self): self.assertEqual(classify(req(production=True, promotion_manifest=promotion_manifest(production=True)))['status'],'HUMAN_REVIEW')
    def test_human_only_target(self): self.assertEqual(classify(req(target_action='PROTECTED_MAIN_MERGE', promotion_manifest=promotion_manifest(target_action='PROTECTED_MAIN_MERGE')))['status'],'HUMAN_REVIEW')
    def test_manifest_identity_tamper_holds(self):
        m=promotion_manifest(candidate_sha='d'*40)
        self.assertEqual(classify(req(promotion_manifest=m))['reason'],'PROMOTION_MANIFEST_IDENTITY_MISMATCH')
    def test_validation_digest_format_tamper_holds(self):
        m=promotion_manifest(validation_package_sha256='x'*64)
        self.assertEqual(classify(req(promotion_manifest=m))['reason'],'PROMOTION_MANIFEST_IDENTITY_MISMATCH')
    def test_rollback_digest_format_tamper_holds(self):
        m=promotion_manifest(rollback_plan_sha256='not-a-digest')
        self.assertEqual(classify(req(promotion_manifest=m))['reason'],'PROMOTION_MANIFEST_IDENTITY_MISMATCH')
    def test_manifest_content_tamper_without_digest_update_holds(self):
        m=promotion_manifest()
        original=m['manifest_sha256']
        m['validation_package_sha256']='3'*64
        self.assertEqual(classify(req(promotion_manifest=m, manifest_sha256=original))['reason'],'PROMOTION_MANIFEST_DIGEST_MISMATCH')
    def test_claimed_manifest_digest_tamper_holds(self):
        m=promotion_manifest()
        m['manifest_sha256']='f'*64
        self.assertEqual(classify(req(promotion_manifest=m, manifest_sha256=_canonical_manifest_digest(m)))['reason'],'PROMOTION_MANIFEST_DIGEST_MISMATCH')
    def test_wrong_external_manifest_digest_holds(self):
        self.assertEqual(classify(req(manifest_sha256='e'*64))['reason'],'PROMOTION_MANIFEST_DIGEST_MISMATCH')
    def test_residual_risks(self): self.assertEqual(build_decision_package(req(residual_risks=('known limitation',)))['recommended_disposition'],'APPROVE_ONLY_IF_RESIDUAL_RISKS_ACCEPTED')
    def test_no_auto_authority(self):
        p=build_decision_package(req())
        self.assertTrue(p['human_decision_required'])
        self.assertEqual(p['auto_approve'],'DISABLED')
        self.assertEqual(p['auto_merge'],'DISABLED')
        self.assertEqual(p['production_deploy'],'DISABLED')
        self.assertTrue(p['evidence_chain']['promotion_manifest_verified'])
        self.assertEqual(p['evidence_chain']['validation_package_sha256'], VAL)
        self.assertEqual(p['evidence_chain']['rollback_plan_sha256'], ROLL)

if __name__ == '__main__': unittest.main()
