from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Optional

AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"

ALLOWED_EVIDENCE_ORIGINS = {"LOM_EVAL", "EXTERNAL_VERIFIED"}
ALLOWED_MODALITIES = {"TEXT", "IMAGE", "AUDIO", "VIDEO", "PDF", "TOOL"}
FORBIDDEN_SECRET_FIELDS = {
    "api_key", "apikey", "token", "access_token", "secret",
    "password", "credential", "credentials", "private_key"
}


@dataclass(frozen=True)
class ModelDescriptor:
    model_id: str
    version: str
    provider: str
    supported: bool
    certified: bool
    security_reviewed: bool
    license_clear: bool
    non_production_only: bool
    modalities: tuple[str, ...]
    tool_use: bool
    evidence_grounding: bool
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True)
class BenchmarkObservation:
    model_id: str
    model_version: str
    task_class: str
    dataset_id: str
    dataset_version: str
    dataset_digest: str
    sample_count: int
    evaluator_id: str
    evidence_origin: str
    evidence_ref: str
    evidence_fresh: bool
    quality: float
    reliability: float
    evidence_correctness: float
    tool_success: float
    hallucination_rate: float
    latency_ms_p50: float
    cost_per_task_usd: float


@dataclass(frozen=True)
class TaskRequest:
    task_class: str
    required_modalities: tuple[str, ...] = ("TEXT",)
    requires_tool_use: bool = False
    requires_evidence_grounding: bool = False
    min_samples: int = 25
    min_quality: float = 0.80
    min_reliability: float = 0.90
    min_evidence_correctness: float = 0.90
    min_tool_success: float = 0.0
    max_hallucination_rate: float = 0.05
    max_latency_ms_p50: Optional[float] = None
    max_cost_per_task_usd: Optional[float] = None
    production: bool = False


def _addressable_ref(value: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and ("://" in text or text.startswith(("urn:", "sha256:")))


def _finite_in_range(value: float, low: float, high: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and low <= float(value) <= high
    )


def _finite_nonnegative(value: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) >= 0
    )


def _base(status: str, reason: str) -> dict:
    return {
        "status": status,
        "reason": reason,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "self_approval": "FORBIDDEN",
    }


class ModelRegistry:
    def __init__(self, descriptors: Iterable[ModelDescriptor]):
        self._models: dict[tuple[str, str], ModelDescriptor] = {}
        for descriptor in descriptors:
            self._validate_descriptor(descriptor)
            key = (descriptor.model_id, descriptor.version)
            if key in self._models:
                raise ValueError("DUPLICATE_MODEL_VERSION")
            self._models[key] = descriptor

    @staticmethod
    def _validate_descriptor(d: ModelDescriptor) -> None:
        if not d.model_id.strip() or not d.version.strip() or not d.provider.strip():
            raise ValueError("MODEL_ID_VERSION_PROVIDER_REQUIRED")
        if not d.modalities:
            raise ValueError("MODEL_MODALITY_REQUIRED")
        if any(m not in ALLOWED_MODALITIES for m in d.modalities):
            raise ValueError("UNKNOWN_MODALITY")
        metadata = dict(d.metadata or {})
        normalized = {str(k).lower().strip() for k in metadata}
        if normalized & FORBIDDEN_SECRET_FIELDS:
            raise ValueError("SECRET_METADATA_FORBIDDEN")

    def get(self, model_id: str, version: str) -> Optional[ModelDescriptor]:
        return self._models.get((model_id, version))

    def eligible_metadata(self, d: ModelDescriptor) -> bool:
        return bool(
            d.supported
            and d.certified
            and d.security_reviewed
            and d.license_clear
            and d.non_production_only
        )


class IntelligenceBenchmark:
    def __init__(self, registry: ModelRegistry, observations: Iterable[BenchmarkObservation]):
        self.registry = registry
        self.observations = tuple(observations)

    def _validate_request(self, r: TaskRequest) -> Optional[dict]:
        if not r.task_class.strip():
            return _base("HOLD", "TASK_CLASS_REQUIRED")
        if r.production:
            return _base("HUMAN_REVIEW", "P0_NON_PRODUCTION_ONLY")
        if not r.required_modalities or any(m not in ALLOWED_MODALITIES for m in r.required_modalities):
            return _base("HOLD", "INVALID_REQUIRED_MODALITY")
        if not isinstance(r.min_samples, int) or isinstance(r.min_samples, bool) or r.min_samples <= 0:
            return _base("HOLD", "INVALID_MIN_SAMPLES")
        rate_fields = (
            r.min_quality,
            r.min_reliability,
            r.min_evidence_correctness,
            r.min_tool_success,
            r.max_hallucination_rate,
        )
        if not all(_finite_in_range(v, 0, 1) for v in rate_fields):
            return _base("HOLD", "INVALID_REQUEST_RATE")
        if r.max_latency_ms_p50 is not None and not _finite_nonnegative(r.max_latency_ms_p50):
            return _base("HOLD", "INVALID_LATENCY_LIMIT")
        if r.max_cost_per_task_usd is not None and not _finite_nonnegative(r.max_cost_per_task_usd):
            return _base("HOLD", "INVALID_COST_LIMIT")
        return None

    @staticmethod
    def _validate_observation(o: BenchmarkObservation) -> Optional[str]:
        required_text = (
            o.model_id, o.model_version, o.task_class, o.dataset_id,
            o.dataset_version, o.dataset_digest, o.evaluator_id
        )
        if not all(str(x).strip() for x in required_text):
            return "BENCHMARK_IDENTITY_INCOMPLETE"
        if o.evidence_origin not in ALLOWED_EVIDENCE_ORIGINS:
            return "UNTRUSTED_BENCHMARK_ORIGIN"
        if not _addressable_ref(o.evidence_ref):
            return "BENCHMARK_EVIDENCE_REQUIRED"
        if not o.evidence_fresh:
            return "BENCHMARK_EVIDENCE_STALE"
        if not isinstance(o.sample_count, int) or isinstance(o.sample_count, bool) or o.sample_count <= 0:
            return "INVALID_SAMPLE_COUNT"
        rates = (
            o.quality, o.reliability, o.evidence_correctness,
            o.tool_success, o.hallucination_rate
        )
        if not all(_finite_in_range(v, 0, 1) for v in rates):
            return "INVALID_BENCHMARK_RATE"
        if not _finite_nonnegative(o.latency_ms_p50):
            return "INVALID_BENCHMARK_LATENCY"
        if not _finite_nonnegative(o.cost_per_task_usd):
            return "INVALID_BENCHMARK_COST"
        return None

    def compile_routes(self, request: TaskRequest) -> dict:
        request_error = self._validate_request(request)
        if request_error:
            return request_error

        eligible: list[tuple[ModelDescriptor, BenchmarkObservation]] = []
        rejection_reasons: dict[str, int] = {}

        for obs in self.observations:
            if obs.task_class != request.task_class:
                continue

            err = self._validate_observation(obs)
            if err:
                rejection_reasons[err] = rejection_reasons.get(err, 0) + 1
                continue

            descriptor = self.registry.get(obs.model_id, obs.model_version)
            if descriptor is None:
                rejection_reasons["MODEL_VERSION_NOT_REGISTERED"] = rejection_reasons.get("MODEL_VERSION_NOT_REGISTERED", 0) + 1
                continue
            if not self.registry.eligible_metadata(descriptor):
                rejection_reasons["MODEL_METADATA_NOT_ELIGIBLE"] = rejection_reasons.get("MODEL_METADATA_NOT_ELIGIBLE", 0) + 1
                continue
            if not set(request.required_modalities).issubset(set(descriptor.modalities)):
                rejection_reasons["MODALITY_MISMATCH"] = rejection_reasons.get("MODALITY_MISMATCH", 0) + 1
                continue
            if request.requires_tool_use and not descriptor.tool_use:
                rejection_reasons["TOOL_USE_REQUIRED"] = rejection_reasons.get("TOOL_USE_REQUIRED", 0) + 1
                continue
            if request.requires_evidence_grounding and not descriptor.evidence_grounding:
                rejection_reasons["EVIDENCE_GROUNDING_REQUIRED"] = rejection_reasons.get("EVIDENCE_GROUNDING_REQUIRED", 0) + 1
                continue
            if obs.sample_count < request.min_samples:
                rejection_reasons["INSUFFICIENT_SAMPLE_COUNT"] = rejection_reasons.get("INSUFFICIENT_SAMPLE_COUNT", 0) + 1
                continue
            if obs.quality < request.min_quality:
                rejection_reasons["QUALITY_GATE_FAILED"] = rejection_reasons.get("QUALITY_GATE_FAILED", 0) + 1
                continue
            if obs.reliability < request.min_reliability:
                rejection_reasons["RELIABILITY_GATE_FAILED"] = rejection_reasons.get("RELIABILITY_GATE_FAILED", 0) + 1
                continue
            if obs.evidence_correctness < request.min_evidence_correctness:
                rejection_reasons["EVIDENCE_GATE_FAILED"] = rejection_reasons.get("EVIDENCE_GATE_FAILED", 0) + 1
                continue
            if obs.tool_success < request.min_tool_success:
                rejection_reasons["TOOL_SUCCESS_GATE_FAILED"] = rejection_reasons.get("TOOL_SUCCESS_GATE_FAILED", 0) + 1
                continue
            if obs.hallucination_rate > request.max_hallucination_rate:
                rejection_reasons["HALLUCINATION_GATE_FAILED"] = rejection_reasons.get("HALLUCINATION_GATE_FAILED", 0) + 1
                continue
            if request.max_latency_ms_p50 is not None and obs.latency_ms_p50 > request.max_latency_ms_p50:
                rejection_reasons["LATENCY_GATE_FAILED"] = rejection_reasons.get("LATENCY_GATE_FAILED", 0) + 1
                continue
            if request.max_cost_per_task_usd is not None and obs.cost_per_task_usd > request.max_cost_per_task_usd:
                rejection_reasons["COST_GATE_FAILED"] = rejection_reasons.get("COST_GATE_FAILED", 0) + 1
                continue

            eligible.append((descriptor, obs))

        if not eligible:
            out = _base("HOLD", "NO_BENCHMARK_ELIGIBLE_MODEL")
            out["rejection_reasons"] = dict(sorted(rejection_reasons.items()))
            return out

        # No global winner. These records are task-scoped inputs for the existing
        # Agentic OS model router. Quality and reliability are primary evidence.
        eligible.sort(
            key=lambda pair: (
                -pair[1].quality,
                -pair[1].reliability,
                -pair[1].evidence_correctness,
                pair[1].hallucination_rate,
                pair[1].latency_ms_p50,
                pair[1].cost_per_task_usd,
                pair[0].model_id,
                pair[0].version,
            )
        )

        routes = []
        for descriptor, obs in eligible:
            route_id = f"{descriptor.provider}:{descriptor.model_id}:{descriptor.version}:{request.task_class}"
            routes.append({
                "route_id": route_id,
                "provider": descriptor.provider,
                "certified": True,
                "supported": True,
                "non_production_only": True,
                "quality": round(obs.quality * 100),
                "reliability": round(obs.reliability * 100),
                # Existing Agentic OS sorts lower latency/cost first after
                # quality/reliability. Use measured values, never synthetic scores.
                "latency": int(round(obs.latency_ms_p50)),
                "cost": int(round(obs.cost_per_task_usd * 1_000_000)),
                "benchmark": {
                    "task_class": obs.task_class,
                    "dataset_id": obs.dataset_id,
                    "dataset_version": obs.dataset_version,
                    "dataset_digest": obs.dataset_digest,
                    "sample_count": obs.sample_count,
                    "evaluator_id": obs.evaluator_id,
                    "evidence_origin": obs.evidence_origin,
                    "evidence_ref": obs.evidence_ref,
                    "evidence_correctness": obs.evidence_correctness,
                    "tool_success": obs.tool_success,
                    "hallucination_rate": obs.hallucination_rate,
                },
            })

        out = _base("ROUTES_READY", "BENCHMARK_GATES_PASSED")
        out.update({
            "task_class": request.task_class,
            "route_count": len(routes),
            "routes": routes,
            "handoff": "vl/lom-agentic-os-p0/intelligence_core.py::ModelRoute",
            "global_winner_declared": False,
        })
        return out
