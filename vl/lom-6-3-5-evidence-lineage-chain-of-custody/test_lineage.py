import unittest
from datetime import datetime, timedelta, timezone

from lineage import LineageRecord, custody_digest, validate_chain, validate_lineage

NOW = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
SHA = 'a' * 40
D1, D2, D3 = '1' * 64, '2' * 64, '3' * 64


def rec(**overrides):
    data = dict(
        workload_id='sabahlot', repository='lundus88/sabahlot', workflow='release-gate.yml',
        run_id=11, artifact_id=22, evidence_sha=SHA,
        raw_evidence_sha256=D1, metrics_sha256=D2, replay_manifest_sha256=D3,
        collected_at=(NOW - timedelta(hours=1)).isoformat(),
        expires_at=(NOW + timedelta(hours=23)).isoformat(),
        run_source_reference='run:11', artifact_source_reference='artifact:22', artifact_retrievable=True,
    )
    data.update(overrides)
    return LineageRecord(**data)


class LineageTests(unittest.TestCase):
    def gate(self, r):
        return validate_lineage(r, expected_workload_id='sabahlot', expected_repository='lundus88/sabahlot', expected_workflow='release-gate.yml', expected_evidence_sha=SHA, now=NOW)

    def chain(self, r, **kw):
        args=dict(replay_claim_raw_sha256=D1,replay_claim_metrics_sha256=D2,replay_manifest_sha256=D3,expected_workload_id='sabahlot',expected_repository='lundus88/sabahlot',expected_workflow='release-gate.yml',expected_evidence_sha=SHA,now=NOW)
        args.update(kw)
        return validate_chain(r, **args)

    def test_ready(self): self.assertEqual(self.gate(rec())['status'], 'READY')
    def test_digest_stable(self): self.assertEqual(custody_digest(rec()), custody_digest(rec()))
    def test_schema(self): self.assertEqual(self.gate(rec(schema='x'))['reason'], 'LINEAGE_SCHEMA_MISMATCH')
    def test_workload(self): self.assertEqual(self.gate(rec(workload_id='x'))['reason'], 'WORKLOAD_MISMATCH')
    def test_source(self): self.assertEqual(self.gate(rec(repository='x'))['reason'], 'SOURCE_IDENTITY_MISMATCH')
    def test_sha(self): self.assertEqual(self.gate(rec(evidence_sha='b'*40))['reason'], 'EVIDENCE_SHA_MISMATCH')
    def test_ids(self): self.assertEqual(self.gate(rec(run_id=0))['reason'], 'RUN_ARTIFACT_ID_REQUIRED')
    def test_digest_format(self): self.assertEqual(self.gate(rec(metrics_sha256='bad'))['reason'], 'INVALID_LINEAGE_DIGEST')
    def test_provenance(self): self.assertEqual(self.gate(rec(run_source_reference=''))['reason'], 'PROVENANCE_REQUIRED')
    def test_retrievable(self): self.assertEqual(self.gate(rec(artifact_retrievable=False))['reason'], 'ARTIFACT_NOT_RETRIEVABLE')
    def test_time_order(self): self.assertEqual(self.gate(rec(expires_at=(NOW-timedelta(hours=2)).isoformat()))['reason'], 'INVALID_CUSTODY_TIME')
    def test_future(self): self.assertEqual(self.gate(rec(collected_at=(NOW+timedelta(minutes=1)).isoformat(), expires_at=(NOW+timedelta(hours=1)).isoformat()))['reason'], 'FUTURE_CUSTODY_RECORD')
    def test_expired(self): self.assertEqual(self.gate(rec(collected_at=(NOW-timedelta(hours=2)).isoformat(), expires_at=NOW.isoformat()))['reason'], 'EVIDENCE_EXPIRED')
    def test_raw_chain(self): self.assertEqual(self.chain(rec(), replay_claim_raw_sha256='4'*64)['reason'], 'RAW_EVIDENCE_LINEAGE_MISMATCH')
    def test_metrics_chain(self): self.assertEqual(self.chain(rec(), replay_claim_metrics_sha256='4'*64)['reason'], 'METRICS_LINEAGE_MISMATCH')
    def test_manifest_chain(self): self.assertEqual(self.chain(rec(), replay_manifest_sha256='4'*64)['reason'], 'REPLAY_MANIFEST_LINEAGE_MISMATCH')
    def test_chain_verified(self): self.assertEqual(self.chain(rec())['reason'], 'CHAIN_OF_CUSTODY_VERIFIED')


if __name__ == '__main__': unittest.main()
