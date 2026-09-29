import math
import unittest

from intelligence_stack import (
    BenchmarkObservation,
    IntelligenceBenchmark,
    ModelDescriptor,
    ModelRegistry,
    TaskRequest,
)


def descriptor(model_id="m1", version="v1", **kw):
    data = dict(
        model_id=model_id,
        version=version,
        provider="provider-a",
        supported=True,
        certified=True,
        security_reviewed=True,
        license_clear=True,
        non_production_only=True,
        modalities=("TEXT", "TOOL"),
        tool_use=True,
        evidence_grounding=True,
        metadata={"family": "test"},
    )
    data.update(kw)
    return ModelDescriptor(**data)


def observation(model_id="m1", version="v1", **kw):
    data = dict(
        model_id=model_id,
        model_version=version,
        task_class="CADASTRAL_REASONING",
        dataset_id="golden-cadastre",
        dataset_version="1",
        dataset_digest="sha256:" + "a" * 64,
        sample_count=100,
        evaluator_id="lom-eval-1",
        evidence_origin="LOM_EVAL",
        evidence_ref="urn:lom:eval:m1:v1:cadastre",
        evidence_fresh=True,
        quality=0.95,
        reliability=0.97,
        evidence_correctness=0.98,
        tool_success=0.96,
        hallucination_rate=0.01,
        latency_ms_p50=1200.0,
        cost_per_task_usd=0.12,
    )
    data.update(kw)
    return BenchmarkObservation(**data)


def request(**kw):
    data = dict(
        task_class="CADASTRAL_REASONING",
        required_modalities=("TEXT",),
        requires_tool_use=True,
        requires_evidence_grounding=True,
        min_samples=50,
        min_quality=0.90,
        min_reliability=0.90,
        min_evidence_correctness=0.95,
        min_tool_success=0.90,
        max_hallucination_rate=0.03,
        max_latency_ms_p50=3000,
        max_cost_per_task_usd=0.50,
        production=False,
    )
    data.update(kw)
    return TaskRequest(**data)


class IntelligenceStackTests(unittest.TestCase):
    def test_compiles_agentic_compatible_route(self):
        board = IntelligenceBenchmark(ModelRegistry([descriptor()]), [observation()])
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "ROUTES_READY")
        self.assertEqual(r["route_count"], 1)
        route = r["routes"][0]
        for key in ("route_id", "provider", "certified", "supported", "non_production_only", "quality", "reliability", "latency", "cost"):
            self.assertIn(key, route)
        self.assertFalse(r["global_winner_declared"])
        self.assertEqual(r["execution_authority"], "NONE")

    def test_exact_version_is_required(self):
        board = IntelligenceBenchmark(ModelRegistry([descriptor(version="v2")]), [observation(version="v1")])
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("MODEL_VERSION_NOT_REGISTERED", r["rejection_reasons"])

    def test_marketing_or_provider_self_report_not_routing_evidence(self):
        board = IntelligenceBenchmark(
            ModelRegistry([descriptor()]),
            [observation(evidence_origin="PROVIDER_MARKETING")]
        )
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("UNTRUSTED_BENCHMARK_ORIGIN", r["rejection_reasons"])

    def test_stale_evidence_fails_closed(self):
        board = IntelligenceBenchmark(ModelRegistry([descriptor()]), [observation(evidence_fresh=False)])
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("BENCHMARK_EVIDENCE_STALE", r["rejection_reasons"])

    def test_quality_and_hallucination_gates(self):
        low = observation(quality=0.50)
        hall = observation(model_id="m2", hallucination_rate=0.20)
        board = IntelligenceBenchmark(
            ModelRegistry([descriptor(), descriptor(model_id="m2")]),
            [low, hall],
        )
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("QUALITY_GATE_FAILED", r["rejection_reasons"])
        self.assertIn("HALLUCINATION_GATE_FAILED", r["rejection_reasons"])

    def test_tool_and_evidence_capability_required(self):
        board = IntelligenceBenchmark(
            ModelRegistry([descriptor(tool_use=False)]),
            [observation()],
        )
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("TOOL_USE_REQUIRED", r["rejection_reasons"])

    def test_production_is_not_authorized_by_p0(self):
        board = IntelligenceBenchmark(ModelRegistry([descriptor()]), [observation()])
        r = board.compile_routes(request(production=True))
        self.assertEqual(r["status"], "HUMAN_REVIEW")
        self.assertEqual(r["production_authority"], "HUMAN_ONLY")

    def test_nonfinite_benchmark_is_rejected(self):
        board = IntelligenceBenchmark(
            ModelRegistry([descriptor()]),
            [observation(quality=math.nan)],
        )
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("INVALID_BENCHMARK_RATE", r["rejection_reasons"])

    def test_registry_forbids_secret_metadata(self):
        with self.assertRaisesRegex(ValueError, "SECRET_METADATA_FORBIDDEN"):
            ModelRegistry([descriptor(metadata={"api_key": "do-not-store"})])

    def test_uncertified_model_never_routes_even_with_superior_metrics(self):
        strong = observation(quality=1.0, reliability=1.0, evidence_correctness=1.0, tool_success=1.0, hallucination_rate=0.0)
        board = IntelligenceBenchmark(
            ModelRegistry([descriptor(certified=False)]),
            [strong],
        )
        r = board.compile_routes(request())
        self.assertEqual(r["status"], "HOLD")
        self.assertIn("MODEL_METADATA_NOT_ELIGIBLE", r["rejection_reasons"])

    def test_task_scoped_ranking_not_global_winner(self):
        obs1 = observation(model_id="m1", quality=0.96, cost_per_task_usd=0.30)
        obs2 = observation(model_id="m2", quality=0.95, reliability=0.99, cost_per_task_usd=0.02)
        board = IntelligenceBenchmark(
            ModelRegistry([
                descriptor(model_id="m1"),
                descriptor(model_id="m2", provider="provider-b"),
            ]),
            [obs1, obs2],
        )
        r = board.compile_routes(request())
        self.assertEqual(r["route_count"], 2)
        self.assertTrue(r["routes"][0]["route_id"].startswith("provider-a:m1:"))
        self.assertFalse(r["global_winner_declared"])


if __name__ == "__main__":
    unittest.main()
