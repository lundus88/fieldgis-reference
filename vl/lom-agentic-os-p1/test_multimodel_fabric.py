import json
from pathlib import Path
from multimodel_fabric import MultiModelFabric, HealthEvidence, RouteRequest

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=json.loads((ROOT/"model-governance"/"model-registry.json").read_text())

def registry():
    r=json.loads(json.dumps(REGISTRY))
    for m in r["models"]:
        m["certified"]=True
        if m["id"].endswith("model-deep-v2"):
            m["quality_score"]=0.97
        elif m["id"].endswith("model-fast-v1"):
            m["quality_score"]=0.90
        else:
            m["quality_score"]=0.80
    return r

def health():
    return [
        HealthEvidence("sandbox-provider-a/model-fast-v1","healthy",1,0.995,900),
        HealthEvidence("sandbox-provider-b/model-deep-v2","healthy",1,0.999,1300),
        HealthEvidence("sandbox-provider-a/model-legacy-v0","healthy",1,0.999,500),
        HealthEvidence("sandbox-provider-b/model-retained-v1","healthy",1,0.999,700),
    ]

def req(**kw):
    base=dict(task_class="analysis",data_class="source_code",input_tokens=10000,output_tokens=2000,
              cost_ceiling=100,autonomy_horizon=1,max_retention="30_days",min_quality=0.5,
              max_latency_ms=5000,max_health_age_hours=24,min_success_rate=0.99)
    base.update(kw)
    return RouteRequest(**base)

def test_deterministic_route_and_digest():
    f=MultiModelFabric(registry(),health())
    a=f.route(req()); b=f.route(req())
    assert a==b and a["decision"]=="ROUTE" and len(a["decision_sha256"])==64

def test_sensitive_data_rejects_retained_model():
    f=MultiModelFabric(registry(),health())
    r=f.route(req(data_class="customer_private",max_retention="none"))
    rejected={x["model_id"]:x["reasons"] for x in r["rejected"]}
    assert "privacy" in rejected["sandbox-provider-b/model-retained-v1"]

def test_stale_health_removes_model():
    h=health()
    h[1]=HealthEvidence("sandbox-provider-b/model-deep-v2","healthy",99,0.999,1300)
    r=MultiModelFabric(registry(),h).route(req())
    rejected={x["model_id"]:x["reasons"] for x in r["rejected"]}
    assert "health_stale" in rejected["sandbox-provider-b/model-deep-v2"]

def test_uncertified_candidate_never_routes():
    rg=registry()
    for m in rg["models"]:
        if m["id"].endswith("model-deep-v2"): m["certified"]=False
    r=MultiModelFabric(rg,health()).route(req(task_class="security_review"))
    assert r["decision"]=="HOLD"
    assert any(x["model_id"].endswith("model-deep-v2") and "uncertified" in x["reasons"] for x in r["rejected"])

def test_quality_bound_fails_closed():
    r=MultiModelFabric(registry(),health()).route(req(min_quality=0.9999))
    assert r["decision"]=="HOLD" and r["reason"]=="NO_ELIGIBLE_ROUTE"

def test_latency_bound_fails_closed():
    r=MultiModelFabric(registry(),health()).route(req(max_latency_ms=100))
    assert r["decision"]=="HOLD"

def test_cost_bound_fails_closed():
    r=MultiModelFabric(registry(),health()).route(req(cost_ceiling=0.0001))
    assert r["decision"]=="HOLD"

def test_fallbacks_are_independently_eligible():
    r=MultiModelFabric(registry(),health()).route(req(task_class="code_generation",max_retention="none"))
    assert r["decision"]=="ROUTE"
    assert "sandbox-provider-a/model-legacy-v0" not in r["fallback_chain"]

def test_no_live_invocation_or_production_authority():
    r=MultiModelFabric(registry(),health()).route(req())
    assert r["production_locked"] is True
    assert r["live_provider_invocation"] is False

if __name__=="__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests: t()
    print(f"PASS {len(tests)} LOM Agentic OS P1 tests")
