from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

SENSITIVE = {"secret","credential","customer_private","proprietary_dataset","production_data"}

def _digest(value: Any) -> str:
    return sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()

@dataclass(frozen=True)
class HealthEvidence:
    model_id: str
    status: str
    age_hours: float
    success_rate: float
    p95_latency_ms: int

@dataclass(frozen=True)
class RouteRequest:
    task_class: str
    data_class: str
    input_tokens: int
    output_tokens: int
    cost_ceiling: float
    autonomy_horizon: int
    max_retention: str
    min_quality: float
    max_latency_ms: int
    max_health_age_hours: float = 24.0
    min_success_rate: float = 0.99

class MultiModelFabric:
    def __init__(self, registry: dict[str, Any], health: Iterable[HealthEvidence]):
        self.registry=registry
        self.health={h.model_id:h for h in health}
        self._validate_registry()

    def _validate_registry(self):
        if self.registry.get("schema") != "vl.model-registry/1":
            raise ValueError("UNSUPPORTED_MODEL_REGISTRY")
        models=self.registry.get("models")
        if not isinstance(models,list) or not models:
            raise ValueError("MODEL_REGISTRY_EMPTY")
        ids=[m.get("id") for m in models]
        if any(not x for x in ids) or len(ids)!=len(set(ids)):
            raise ValueError("MODEL_ID_INVALID")

    @staticmethod
    def _retention_rank(value: str) -> int:
        ranks={"none":0,"session":1,"30_days":2}
        if value not in ranks:
            raise ValueError("INVALID_RETENTION_POLICY")
        return ranks[value]

    def _privacy_ok(self, model: dict[str,Any], req: RouteRequest) -> bool:
        privacy=model.get("privacy") or {}
        if privacy.get("training") != "disabled":
            return False
        retention=privacy.get("retention")
        if req.data_class in SENSITIVE:
            return retention == "none"
        return self._retention_rank(retention) <= self._retention_rank(req.max_retention)

    def _health_ok(self, model_id: str, req: RouteRequest) -> tuple[bool,list[str]]:
        h=self.health.get(model_id)
        if h is None:
            return False,["health_missing"]
        reasons=[]
        if h.status != "healthy": reasons.append("health_status")
        if h.age_hours < 0 or h.age_hours > req.max_health_age_hours: reasons.append("health_stale")
        if not (0 <= h.success_rate <= 1) or h.success_rate < req.min_success_rate: reasons.append("success_slo")
        if h.p95_latency_ms < 0 or h.p95_latency_ms > req.max_latency_ms: reasons.append("latency_slo")
        return not reasons,reasons

    def route(self, req: RouteRequest) -> dict[str,Any]:
        if min(req.input_tokens,req.output_tokens,req.cost_ceiling,req.autonomy_horizon,req.min_quality,req.max_latency_ms,req.max_health_age_hours,req.min_success_rate) < 0:
            return {"decision":"HOLD","reason":"INVALID_REQUIREMENT","production_locked":True}
        if req.min_success_rate > 1:
            return {"decision":"HOLD","reason":"INVALID_SUCCESS_RATE","production_locked":True}

        candidates=[]
        rejected=[]
        for model in self.registry["models"]:
            reasons=[]
            mid=model["id"]
            if model.get("status") != "active": reasons.append("status")
            if req.task_class not in (model.get("task_classes") or []): reasons.append("task_class")
            if req.input_tokens > model.get("max_input_tokens",-1): reasons.append("input_tokens")
            if req.output_tokens > model.get("max_output_tokens",-1): reasons.append("output_tokens")
            if req.autonomy_horizon > model.get("max_autonomy_horizon",-1): reasons.append("autonomy_horizon")
            if not self._privacy_ok(model,req): reasons.append("privacy")

            quality=float(model.get("quality_score",0))
            if quality < req.min_quality: reasons.append("quality")

            est=((req.input_tokens+req.output_tokens)/1000.0)*float(model.get("estimated_cost_per_1k_tokens",-1))
            if est < 0 or est > req.cost_ceiling: reasons.append("cost")

            health_ok, health_reasons=self._health_ok(mid,req)
            if not health_ok: reasons.extend(health_reasons)

            certified = model.get("certified", True)
            if certified is not True: reasons.append("uncertified")

            if reasons:
                rejected.append({"model_id":mid,"reasons":sorted(set(reasons))})
                continue

            h=self.health[mid]
            score=(quality*1000.0)+(h.success_rate*100.0)-(h.p95_latency_ms/1000.0)-est
            candidates.append((score,mid,round(est,8),h.p95_latency_ms,quality))

        if not candidates:
            evidence={
                "schema":"lom.multimodel-route-evidence/1",
                "decision":"HOLD",
                "reason":"NO_ELIGIBLE_ROUTE",
                "rejected":sorted(rejected,key=lambda x:x["model_id"]),
                "production_locked":True,
            }
            evidence["decision_sha256"]=_digest(evidence)
            return evidence

        candidates.sort(key=lambda x:(-x[0],x[1]))
        selected=candidates[0]
        fallbacks=[x[1] for x in candidates[1:]]
        body={
            "schema":"lom.multimodel-route-evidence/1",
            "decision":"ROUTE",
            "reason":"ELIGIBLE_ROUTE_SELECTED",
            "registry_id":self.registry.get("registry_id"),
            "registry_version":self.registry.get("version"),
            "request_sha256":_digest(req.__dict__),
            "selected_model_id":selected[1],
            "estimated_cost":selected[2],
            "fallback_chain":fallbacks,
            "rejected":sorted(rejected,key=lambda x:x["model_id"]),
            "deterministic":True,
            "production_locked":True,
            "live_provider_invocation":False,
        }
        return {**body,"decision_sha256":_digest(body)}
