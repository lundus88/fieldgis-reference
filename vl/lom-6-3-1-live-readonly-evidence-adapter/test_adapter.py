import unittest
from datetime import datetime, timedelta, timezone

from adapter import EvidenceSource, WorkflowRunEvidence, TechnicalMetricsArtifact, access_policy, validate_run, promote_metrics

NOW = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
SHA = 'a' * 40


def source(**overrides):
    data = dict(workload_id='sabahlot', repository='lundus88/sabahlot', workflow='release-gate.yml', visibility='public', production_sensitive=False)
    data.update(overrides)
    return EvidenceSource(**data)


def run(**overrides):
    data = dict(repository='lundus88/sabahlot', workflow='release-gate.yml', run_id=10, head_sha=SHA, status='completed', conclusion='success', updated_at=(NOW - timedelta(hours=1)).isoformat(), source_reference='actions/run/10')
    data.update(overrides)
    return WorkflowRunEvidence(**data)


def metrics(**overrides):
    data = dict(evidence_sha=SHA, sample_count=20, success_rate=.99, correctness=.98, safety=.999, p95_latency_ms=1200, source_reference='artifact/metrics-10')
    data.update(overrides)
    return TechnicalMetricsArtifact(**data)


class AdapterTests(unittest.TestCase):
    def test_public_access_ready(self):
        self.assertEqual(access_policy(source(), readonly_credential_available=False)['status'], 'READY')

    def test_private_without_credential_holds(self):
        s = source(visibility='private')
        self.assertEqual(access_policy(s, readonly_credential_available=False)['reason'], 'READ_CREDENTIAL_REQUIRED')

    def test_private_with_readonly_credential_ready(self):
        s = source(visibility='private')
        self.assertEqual(access_policy(s, readonly_credential_available=True)['status'], 'READY')

    def test_production_sensitive_forbidden(self):
        s = source(production_sensitive=True)
        self.assertEqual(access_policy(s, readonly_credential_available=True)['reason'], 'PRODUCTION_SENSITIVE_SOURCE_FORBIDDEN')

    def test_source_identity_mismatch_holds(self):
        self.assertEqual(validate_run(source(), run(workflow='other.yml'), expected_sha=SHA, now=NOW)['reason'], 'SOURCE_IDENTITY_MISMATCH')

    def test_sha_mismatch_holds(self):
        self.assertEqual(validate_run(source(), run(head_sha='b'*40), expected_sha=SHA, now=NOW)['reason'], 'EVIDENCE_SHA_MISMATCH')

    def test_unsuccessful_run_holds(self):
        self.assertEqual(validate_run(source(), run(conclusion='failure'), expected_sha=SHA, now=NOW)['reason'], 'WORKFLOW_RUN_NOT_SUCCESSFUL')

    def test_stale_run_holds(self):
        r = run(updated_at=(NOW - timedelta(hours=49)).isoformat())
        self.assertEqual(validate_run(source(), r, expected_sha=SHA, now=NOW)['reason'], 'STALE_OR_FUTURE_RUN')

    def test_live_run_ready(self):
        self.assertEqual(validate_run(source(), run(), expected_sha=SHA, now=NOW)['status'], 'READY')

    def test_missing_metrics_holds(self):
        out = promote_metrics(source(), run(), None, expected_sha=SHA, readonly_credential_available=False, now=NOW)
        self.assertEqual(out['reason'], 'TECHNICAL_METRICS_ARTIFACT_REQUIRED')

    def test_metrics_sha_mismatch_holds(self):
        out = promote_metrics(source(), run(), metrics(evidence_sha='b'*40), expected_sha=SHA, readonly_credential_available=False, now=NOW)
        self.assertEqual(out['reason'], 'METRICS_SHA_MISMATCH')

    def test_invalid_rates_hold(self):
        out = promote_metrics(source(), run(), metrics(safety=1.2), expected_sha=SHA, readonly_credential_available=False, now=NOW)
        self.assertEqual(out['reason'], 'INVALID_RATE')

    def test_invalid_latency_holds(self):
        out = promote_metrics(source(), run(), metrics(p95_latency_ms=-1), expected_sha=SHA, readonly_credential_available=False, now=NOW)
        self.assertEqual(out['reason'], 'METRICS_PROVENANCE_REQUIRED')

    def test_valid_metrics_promote_ready(self):
        out = promote_metrics(source(), run(), metrics(), expected_sha=SHA, readonly_credential_available=False, now=NOW)
        self.assertEqual(out['status'], 'READY')
        self.assertEqual(out['measurement']['source_kind'], 'ci_artifact')

    def test_private_source_remains_hold_without_credential_even_with_metrics(self):
        s = source(visibility='private')
        out = promote_metrics(s, run(), metrics(), expected_sha=SHA, readonly_credential_available=False, now=NOW)
        self.assertEqual(out['reason'], 'READ_CREDENTIAL_REQUIRED')

    def test_adapter_never_enables_write_or_production(self):
        out = promote_metrics(source(), run(), metrics(), expected_sha=SHA, readonly_credential_available=False, now=NOW)
        self.assertEqual(out['cross_repo_write'], 'DISABLED')
        self.assertEqual(out['production_action'], 'DISABLED')


if __name__ == '__main__':
    unittest.main()
