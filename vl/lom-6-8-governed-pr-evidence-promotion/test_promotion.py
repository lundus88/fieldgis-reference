import unittest
from promotion import PromotionRequest, build_promotion_package, manifest_digest, validate_promotion

D1='1'*64
D2='2'*64


def req(**overrides):
    base = dict(
        workload_id='ebkl',
        base_sha='a'*40,
        candidate_sha='b'*40,
        evidence_sha='c'*40,
        source_reference='ci://lom-6-7/run/1',
        validation_status='PREPARE_PR',
        validation_package_sha256=D1,
        rollback_plan_digest=D2,
        target_action='NON_PRODUCTION_REVERSIBLE_ACTION',
        production=False,
        risk='LOW',
    )
    base.update(overrides)
    return PromotionRequest(**base)


class PromotionGateTests(unittest.TestCase):
    def test_ready_candidate(self):
        self.assertEqual(validate_promotion(req())['status'], 'PREPARE_PR')

    def test_missing_workload_holds(self):
        self.assertEqual(validate_promotion(req(workload_id=''))['reason'], 'WORKLOAD_ID_REQUIRED')

    def test_bad_base_sha_holds(self):
        self.assertEqual(validate_promotion(req(base_sha='bad'))['reason'], 'EXACT_SHA_REQUIRED')

    def test_bad_candidate_sha_holds(self):
        self.assertEqual(validate_promotion(req(candidate_sha='bad'))['reason'], 'EXACT_SHA_REQUIRED')

    def test_bad_evidence_sha_holds(self):
        self.assertEqual(validate_promotion(req(evidence_sha='bad'))['reason'], 'EXACT_SHA_REQUIRED')

    def test_same_base_candidate_holds(self):
        self.assertEqual(validate_promotion(req(candidate_sha='a'*40))['reason'], 'CANDIDATE_MUST_DIFFER_FROM_BASE')

    def test_missing_source_holds(self):
        self.assertEqual(validate_promotion(req(source_reference=''))['reason'], 'SOURCE_REFERENCE_REQUIRED')

    def test_non_prepare_validation_holds(self):
        self.assertEqual(validate_promotion(req(validation_status='HOLD'))['reason'], 'SANDBOX_VALIDATION_REQUIRED')

    def test_missing_validation_package_digest_holds(self):
        self.assertEqual(validate_promotion(req(validation_package_sha256=''))['reason'], 'VALIDATION_PACKAGE_DIGEST_REQUIRED')

    def test_non_sha256_validation_package_digest_holds(self):
        self.assertEqual(validate_promotion(req(validation_package_sha256='x'*64))['reason'], 'VALIDATION_PACKAGE_DIGEST_REQUIRED')

    def test_missing_rollback_holds(self):
        self.assertEqual(validate_promotion(req(rollback_plan_digest=''))['reason'], 'ROLLBACK_PLAN_DIGEST_REQUIRED')

    def test_non_sha256_rollback_holds(self):
        self.assertEqual(validate_promotion(req(rollback_plan_digest='rollback-digest-1234567890'))['reason'], 'ROLLBACK_PLAN_DIGEST_REQUIRED')

    def test_unknown_risk_holds(self):
        self.assertEqual(validate_promotion(req(risk='UNKNOWN'))['reason'], 'UNKNOWN_RISK')

    def test_high_risk_human_review(self):
        self.assertEqual(validate_promotion(req(risk='HIGH'))['status'], 'HUMAN_REVIEW')

    def test_production_human_review(self):
        self.assertEqual(validate_promotion(req(production=True))['status'], 'HUMAN_REVIEW')

    def test_human_only_target_human_review(self):
        self.assertEqual(validate_promotion(req(target_action='PROTECTED_MAIN_MERGE'))['status'], 'HUMAN_REVIEW')

    def test_manifest_digest_is_deterministic(self):
        self.assertEqual(manifest_digest(req()), manifest_digest(req()))

    def test_manifest_digest_changes_with_candidate(self):
        self.assertNotEqual(manifest_digest(req()), manifest_digest(req(candidate_sha='d'*40)))

    def test_manifest_digest_changes_with_validation_package(self):
        self.assertNotEqual(manifest_digest(req()), manifest_digest(req(validation_package_sha256='3'*64)))

    def test_manifest_digest_changes_with_rollback_plan(self):
        self.assertNotEqual(manifest_digest(req()), manifest_digest(req(rollback_plan_digest='4'*64)))

    def test_package_preserves_human_merge_boundary(self):
        package = build_promotion_package(req())
        self.assertTrue(package['pr_candidate']['human_merge_required'])
        self.assertEqual(package['auto_merge'], 'DISABLED')
        self.assertEqual(package['production_execution'], 'DISABLED')
        self.assertEqual(package['schema'], 'lom.pr-evidence-promotion-package/2')
        self.assertEqual(package['manifest']['schema'], 'lom.pr-evidence-promotion/2')
        self.assertEqual(package['evidence_chain']['validation_package_sha256'], D1)
        self.assertEqual(package['evidence_chain']['rollback_plan_sha256'], D2)
        self.assertEqual(len(package['manifest']['manifest_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
