import unittest
from sandbox import ValidationRequest, validate, validation_package


def req(**overrides):
    data = dict(
        workload_id='ebkl', evidence_sha='a'*40, source_reference='ci:123', evidence_fresh=True,
        target_action='NON_PRODUCTION_REVERSIBLE_ACTION', risk='LOW', reversible=True, production=False,
        ephemeral=True, network_disabled=True, production_credentials_absent=True,
        rollback_plan_present=True, build_passed=True, regression_passed=True,
        security_passed=True, independent_validation_passed=True,
    )
    data.update(overrides)
    return ValidationRequest(**data)


class SandboxTests(unittest.TestCase):
    def test_valid_prepare_pr(self): self.assertEqual(validate(req())['status'], 'PREPARE_PR')
    def test_workload_required(self): self.assertEqual(validate(req(workload_id=''))['status'], 'HOLD')
    def test_evidence_fresh(self): self.assertEqual(validate(req(evidence_fresh=False))['status'], 'HOLD')
    def test_evidence_sha(self): self.assertEqual(validate(req(evidence_sha=None))['status'], 'HOLD')
    def test_source_required(self): self.assertEqual(validate(req(source_reference=None))['status'], 'HOLD')
    def test_human_only(self): self.assertEqual(validate(req(target_action='PRODUCTION_RELEASE'))['status'], 'HUMAN_REVIEW')
    def test_production(self): self.assertEqual(validate(req(production=True))['status'], 'HUMAN_REVIEW')
    def test_high_risk(self): self.assertEqual(validate(req(risk='HIGH'))['status'], 'HUMAN_REVIEW')
    def test_unknown_risk(self): self.assertEqual(validate(req(risk='UNKNOWN'))['status'], 'HOLD')
    def test_reversible_required(self): self.assertEqual(validate(req(reversible=False))['status'], 'HOLD')
    def test_ephemeral_required(self): self.assertEqual(validate(req(ephemeral=False))['status'], 'HOLD')
    def test_network_disabled(self): self.assertEqual(validate(req(network_disabled=False))['status'], 'HOLD')
    def test_prod_creds_forbidden(self): self.assertEqual(validate(req(production_credentials_absent=False))['status'], 'HOLD')
    def test_rollback_required(self): self.assertEqual(validate(req(rollback_plan_present=False))['status'], 'HOLD')
    def test_failed_checks_hold(self):
        d = validate(req(build_passed=False, security_passed=False))
        self.assertEqual(d['status'], 'HOLD')
        self.assertEqual(d['failed_checks'], ['build', 'security'])
    def test_package_boundaries(self):
        p = validation_package(req())
        self.assertEqual(p['autonomous_ceiling'], 'PREPARE_PR')
        self.assertEqual(p['production_authority'], 'HUMAN_ONLY')
        self.assertEqual(p['auto_merge'], 'DISABLED')
        self.assertEqual(p['production_execution'], 'DISABLED')

if __name__ == '__main__':
    unittest.main()
