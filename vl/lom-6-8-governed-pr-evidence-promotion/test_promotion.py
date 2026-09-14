import unittest
from promotion import PromotionRequest, build_promotion_package, manifest_digest, validate_promotion


def req(**overrides):
    base = dict(
        workload_id='ebkl',
        base_sha='a'*40,
        candidate_sha='b'*40,
        evidence_sha='c'*40,
        source_reference='ci://lom-6-7/run/1',
        validation_status='PREPARE_PR',
        rollback_plan_digest='rollback-digest-1234567890',
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

    def test_missing_rollback_holds(self):
        self.assertEqual(validate_promotion(req(rollback_plan_digest=''))['reason'], 'ROLLBACK_EVIDENCE_REQUIRED')

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

    def test_package_preserves_human_merge_boundary(self):
        package = build_promotion_package(req())
        self.assertTrue(package['pr_candidate']['human_merge_required'])
        self.assertEqual(package['auto_merge'], 'DISABLED')
        self.assertEqual(package['production_execution'], 'DISABLED')
        self.assertEqual(len(package['manifest']['manifest_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
