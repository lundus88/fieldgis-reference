import unittest

from evidence_fabric import (
    OperationalEvidence,
    TechnicalMetrics,
    build_fabric_snapshot,
    truth_candidate_index,
    validate_evidence,
    validate_fabric_snapshot,
)

NOW = 2_000_000_000
SHA = "a" * 40
SHA2 = "b" * 40


def registry():
    return {
        "version": "2.0",
        "sources": [
            {
                "project_id": "ebkl",
                "name": "e-BKL",
                "objective_id": "portfolio:ebkl:readiness",
                "repository": "lundus88/ebkl",
                "default_branch": "main",
                "mode": "READ_ONLY",
            },
            {
                "project_id": "slp",
                "name": "SLP",
                "objective_id": "portfolio:slp:readiness",
                "repository": None,
                "default_branch": None,
                "mode": "UNREGISTERED_HOLD",
                "hold_reason": "AUTHORITATIVE_SOURCE_NOT_REGISTERED",
            },
        ],
    }


def evidence(signal_type, **overrides):
    data = dict(
        project_id="ebkl",
        objective_id="portfolio:ebkl:readiness",
        repository="lundus88/ebkl",
        evidence_sha=SHA,
        signal_type=signal_type,
        result="PASS",
        observed_at_epoch=NOW - 100,
        source_reference=f"evidence:{signal_type.lower()}:1",
    )
    if signal_type == "DEPLOYMENT_STATE":
        data["deployment_state"] = "PREVIEW"
    if signal_type == "BACKGROUND_JOB":
        data["job_status"] = "SUCCESS"
    data.update(overrides)
    return OperationalEvidence(**data)


class EvidenceFabricTests(unittest.TestCase):
    def test_complete_minimum_nonindependent_stays_unverified(self):
        snap = build_fabric_snapshot(
            registry(),
            [evidence("CI_RUN"), evidence("RUNTIME_HEALTH")],
            now_epoch=NOW,
        )
        item = truth_candidate_index(snap)["ebkl"]
        self.assertEqual(item["status"], "READY")
        self.assertEqual(item["truth_candidate"], "UNVERIFIED")
        self.assertEqual(item["reason"], "INDEPENDENT_VALIDATION_REQUIRED")

    def test_independent_minimum_becomes_verified_candidate(self):
        snap = build_fabric_snapshot(
            registry(),
            [evidence("CI_RUN", independent=True), evidence("RUNTIME_HEALTH")],
            now_epoch=NOW,
        )
        item = truth_candidate_index(snap)["ebkl"]
        self.assertEqual(item["truth_candidate"], "VERIFIED")
        self.assertTrue(item["independent_validation"])

    def test_missing_required_signal_holds(self):
        snap = build_fabric_snapshot(registry(), [evidence("CI_RUN")], now_epoch=NOW)
        item = truth_candidate_index(snap)["ebkl"]
        self.assertEqual((item["status"], item["reason"]), ("HOLD", "REQUIRED_OPERATIONAL_SIGNAL_MISSING"))
        self.assertEqual(item["missing_required_signals"], ["RUNTIME_HEALTH"])

    def test_stale_evidence_holds(self):
        stale = evidence("CI_RUN", observed_at_epoch=NOW - 200_000)
        source = registry()["sources"][0]
        self.assertEqual(
            validate_evidence(stale, source, now_epoch=NOW, max_age_seconds=100)["reason"],
            "STALE_OPERATIONAL_EVIDENCE",
        )

    def test_production_sensitive_evidence_holds(self):
        source = registry()["sources"][0]
        decision = validate_evidence(evidence("CI_RUN", production_sensitive=True), source, now_epoch=NOW)
        self.assertEqual(decision["reason"], "PRODUCTION_SENSITIVE_EVIDENCE_FORBIDDEN")

    def test_failure_evidence_fails_project(self):
        snap = build_fabric_snapshot(
            registry(),
            [evidence("CI_RUN"), evidence("RUNTIME_HEALTH", result="FAIL")],
            now_epoch=NOW,
        )
        item = truth_candidate_index(snap)["ebkl"]
        self.assertEqual((item["status"], item["truth_candidate"]), ("FAILED", "FAILED"))

    def test_unregistered_source_fails_closed(self):
        snap = build_fabric_snapshot(registry(), [], now_epoch=NOW)
        item = truth_candidate_index(snap)["slp"]
        self.assertEqual(item["status"], "HOLD")
        self.assertEqual(item["reason"], "AUTHORITATIVE_SOURCE_NOT_REGISTERED")

    def test_unknown_project_evidence_is_quarantined(self):
        unknown = OperationalEvidence(
            project_id="unknown",
            objective_id="portfolio:unknown:readiness",
            repository="lundus88/unknown",
            evidence_sha=SHA,
            signal_type="CI_RUN",
            result="PASS",
            observed_at_epoch=NOW - 10,
            source_reference="run:1",
        )
        snap = build_fabric_snapshot(registry(), [unknown], now_epoch=NOW)
        self.assertEqual(snap["overall"], "HOLD")
        self.assertEqual(snap["unknown_evidence"][0]["reason"], "EVIDENCE_PROJECT_NOT_REGISTERED")

    def test_metrics_are_normalized_by_existing_telemetry_collector(self):
        metrics = TechnicalMetrics(
            sample_count=20,
            success_rate=1.0,
            correctness=1.0,
            safety=1.0,
            p95_latency_ms=250,
        )
        source = registry()["sources"][0]
        decision = validate_evidence(evidence("RUNTIME_HEALTH", technical_metrics=metrics), source, now_epoch=NOW)
        self.assertEqual(decision["status"], "READY")
        self.assertEqual(decision["metrics_health"], "MONITOR")

    def test_unsafe_metrics_require_human_review(self):
        metrics = TechnicalMetrics(
            sample_count=20,
            success_rate=1.0,
            correctness=1.0,
            safety=0.90,
            p95_latency_ms=250,
        )
        source = registry()["sources"][0]
        decision = validate_evidence(evidence("RUNTIME_HEALTH", technical_metrics=metrics), source, now_epoch=NOW)
        self.assertEqual((decision["status"], decision["reason"]), ("HOLD", "TECHNICAL_METRICS_HUMAN_REVIEW"))

    def test_conflicting_same_signal_holds(self):
        snap = build_fabric_snapshot(
            registry(),
            [
                evidence("CI_RUN"),
                evidence("CI_RUN", result="FAIL"),
                evidence("RUNTIME_HEALTH"),
            ],
            now_epoch=NOW,
        )
        item = truth_candidate_index(snap)["ebkl"]
        self.assertEqual(item["reason"], "CONTRADICTORY_OPERATIONAL_EVIDENCE")

    def test_required_signal_sha_set_mismatch_holds(self):
        snap = build_fabric_snapshot(
            registry(),
            [evidence("CI_RUN"), evidence("RUNTIME_HEALTH", evidence_sha=SHA2)],
            now_epoch=NOW,
        )
        item = truth_candidate_index(snap)["ebkl"]
        self.assertEqual(item["reason"], "EVIDENCE_SHA_SET_MISMATCH")

    def test_recommended_gaps_are_explicit(self):
        snap = build_fabric_snapshot(
            registry(),
            [evidence("CI_RUN", independent=True), evidence("RUNTIME_HEALTH")],
            now_epoch=NOW,
        )
        item = truth_candidate_index(snap)["ebkl"]
        self.assertEqual(item["missing_recommended_signals"], ["AUTH_PATH", "BACKGROUND_JOB", "DEPLOYMENT_STATE"])

    def test_deployment_and_job_state_are_scope_checked(self):
        source = registry()["sources"][0]
        self.assertEqual(validate_evidence(evidence("DEPLOYMENT_STATE"), source, now_epoch=NOW)["status"], "READY")
        self.assertEqual(validate_evidence(evidence("BACKGROUND_JOB"), source, now_epoch=NOW)["status"], "READY")
        bad = evidence("CI_RUN", deployment_state="READY")
        self.assertEqual(validate_evidence(bad, source, now_epoch=NOW)["reason"], "DEPLOYMENT_STATE_SCOPE_MISMATCH")

    def test_snapshot_fingerprint_tamper_holds(self):
        snap = build_fabric_snapshot(registry(), [], now_epoch=NOW)
        self.assertEqual(validate_fabric_snapshot(snap)["status"], "READY")
        snap["projects"][0]["status"] = "READY"
        self.assertEqual(validate_fabric_snapshot(snap)["reason"], "FABRIC_FINGERPRINT_MISMATCH")

    def test_authority_contract_is_read_only(self):
        snap = build_fabric_snapshot(registry(), [], now_epoch=NOW)
        self.assertEqual(snap["autonomous_ceiling"], "PREPARE_PR")
        self.assertEqual(snap["production_authority"], "HUMAN_ONLY")
        self.assertEqual(snap["execution_authority"], "NONE")
        self.assertFalse(snap["execution_performed"])
        self.assertEqual(snap["cross_repo_write"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
