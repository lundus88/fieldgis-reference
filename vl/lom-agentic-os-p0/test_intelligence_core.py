from intelligence_core import IntelligenceCore, ToolSpec, ModelRoute, Objective, assess_frontier_capability

def core():
    return IntelligenceCore(
        tools=[
            ToolSpec("readonly.search","cap.observe.readonly",True,True,"LOW"),
            ToolSpec("unsafe.prod","cap.prod",True,False,"HIGH"),
        ],
        routes=[
            ModelRoute("route-a","vendor-a",True,True,True,95,94,20,30),
            ModelRoute("route-b","vendor-b",True,True,True,92,99,10,10),
            ModelRoute("route-uncertified","vendor-x",False,True,True,100,100,1,1),
        ],
    )

def test_unknown_tool_fails_closed():
    o=Objective("o1","READ_ONLY_OBSERVATION","cap.observe.readonly",("ev1",),"missing")
    assert core().plan(o)["reason"]=="UNKNOWN_TOOL"

def test_human_only_action_routes_human_gate():
    o=Objective("o2","PRODUCTION_RELEASE","cap.prod",("ev1",),"unsafe.prod")
    r=core().plan(o)
    assert r["decision"]=="HUMAN_GATE"
    assert r["reason"]=="HUMAN_ONLY_ACTION"

def test_missing_evidence_holds():
    o=Objective("o3","READ_ONLY_OBSERVATION","cap.observe.readonly",(),"readonly.search")
    assert core().plan(o)["reason"]=="EVIDENCE_REQUIRED"

def test_router_ignores_uncertified_superior_score():
    o=Objective("o4","READ_ONLY_OBSERVATION","cap.observe.readonly",("ev1",),"readonly.search")
    r=core().plan(o)
    assert r["decision"]=="ALLOW"
    assert r["route_id"]=="route-a"
    assert r["plan_digest"]

def test_checkpoint_requires_evidence():
    o=Objective("o5","READ_ONLY_OBSERVATION","cap.observe.readonly",("ev1",),"readonly.search")
    p=core().plan(o)
    assert core().checkpoint(o,p,(),"EXECUTED")["reason"]=="CHECKPOINT_EVIDENCE_REQUIRED"

def test_executor_cannot_self_verify():
    o=Objective("o6","READ_ONLY_OBSERVATION","cap.observe.readonly",("ev1",),"readonly.search")
    p=core().plan(o)
    cp=core().checkpoint(o,p,("run-ev",),"EXECUTED")
    r=core().verify_completion(cp,"agent-x","agent-x",("verify-ev",))
    assert r["reason"]=="INDEPENDENT_VERIFIER_REQUIRED"

def test_independent_verification_succeeds():
    o=Objective("o7","READ_ONLY_OBSERVATION","cap.observe.readonly",("ev1",),"readonly.search")
    p=core().plan(o)
    cp=core().checkpoint(o,p,("run-ev",),"EXECUTED")
    r=core().verify_completion(cp,"verifier","executor",("verify-ev",))
    assert r["decision"]=="ALLOW"
    assert r["verification_digest"]

def test_frontier_intake_is_conservative():
    assert assess_frontier_capability(
        source_official=True, security_reviewed=True, license_clear=True,
        measurable_value=True, production_authority_required=False
    )=="PILOT"
    assert assess_frontier_capability(
        source_official=False, security_reviewed=True, license_clear=True,
        measurable_value=True, production_authority_required=False
    )=="REJECT"

if __name__ == "__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} LOM Agentic OS P0 tests")
