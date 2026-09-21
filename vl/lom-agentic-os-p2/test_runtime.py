import os
import tempfile
from runtime import Observation, Eyes, ActionRequest, ActionAdapter, Hands, ContinuityStore, Runtime

NOW=1_000_000.0

def fresh_observation():
    return Observation("github",NOW-5,60,{"head":"abc123"},"evidence:github:1")

def stale_observation():
    return Observation("github",NOW-500,60,{"head":"old"},"evidence:github:old")

def execute(req):
    return {"mode":"dry-run" if req.dry_run else "nonprod-write","prepared":True}

def verify(req,result):
    return {"decision":"ALLOW" if result.get("prepared") else "HOLD","evidence_id":"verify:1"}

def hands():
    return Hands({"repo.prepare_pr":ActionAdapter("repo.prepare_pr",True,True,execute,verify)})

def request(**kw):
    base=dict(
        request_id="r1",action_id="PREPARE_PR",capability_id="repo.prepare_pr",
        idempotency_key="idem-1",environment="development",risk="LOW",dry_run=True,
        evidence_ids=("e1",)
    )
    base.update(kw)
    return ActionRequest(**base)

def test_eyes_fresh_and_digest_bound():
    r=Eyes({"github":fresh_observation}).observe(["github"],NOW)
    assert r["decision"]=="ALLOW"
    assert len(r["snapshot_digest"])==64

def test_eyes_fail_closed_on_stale_source():
    r=Eyes({"github":stale_observation}).observe(["github"],NOW)
    assert r["decision"]=="HOLD" and r["reason"]=="STALE_OBSERVATION"

def test_hands_human_gate_for_production():
    r=hands().act(request(environment="production"))
    assert r["decision"]=="HUMAN_GATE" and r["production_locked"] is True

def test_hands_human_gate_for_consequential_action():
    r=hands().act(request(action_id="PROTECTED_MAIN_MERGE"))
    assert r["decision"]=="HUMAN_GATE"

def test_hands_idempotency_replays_same_result():
    h=hands()
    a=h.act(request())
    b=h.act(request())
    assert a["decision"]=="ALLOW"
    assert b["decision"]=="ALLOW" and b["replayed"] is True
    assert a["action_digest"]==b["action_digest"]

def test_continuity_checkpoint_resume_survives_reopen():
    fd,path=tempfile.mkstemp(prefix="lom-p2-",suffix=".sqlite3")
    os.close(fd)
    try:
        s=ContinuityStore(path)
        cp=s.checkpoint("obj-1",{"step":3},NOW)
        assert cp["decision"]=="ALLOW"
        s.db.close()
        s2=ContinuityStore(path)
        r=s2.resume("obj-1")
        assert r["decision"]=="ALLOW" and r["state"]["step"]==3
        assert all(x["digest_valid"] for x in s2.events("obj-1"))
    finally:
        try: os.remove(path)
        except FileNotFoundError: pass

def test_lease_prevents_duplicate_worker_and_allows_expiry_takeover():
    s=ContinuityStore()
    a=s.acquire_lease("obj","worker-a",30,NOW)
    b=s.acquire_lease("obj","worker-b",30,NOW+10)
    c=s.acquire_lease("obj","worker-b",30,NOW+31)
    assert a["decision"]=="ALLOW"
    assert b["decision"]=="HOLD" and b["reason"]=="LEASE_HELD"
    assert c["decision"]=="ALLOW"

def test_runtime_cycle_persists_checkpoint_and_evidence():
    rt=Runtime(Eyes({"github":fresh_observation}),hands(),ContinuityStore())
    r=rt.cycle(objective_id="obj",owner_id="worker-a",source_ids=["github"],action=request(),state={"phase":"prepare"},lease_seconds=60,now=NOW)
    assert r["decision"]=="ALLOW" and r["production_locked"] is True
    resumed=rt.continuity.resume("obj")
    assert resumed["decision"]=="ALLOW"
    assert resumed["state"]["state"]["phase"]=="prepare"
    assert resumed["state"]["action_digest"]==r["action_digest"]

def test_runtime_stops_before_action_when_observation_is_stale():
    rt=Runtime(Eyes({"github":stale_observation}),hands(),ContinuityStore())
    r=rt.cycle(objective_id="obj",owner_id="worker-a",source_ids=["github"],action=request(),state={},lease_seconds=60,now=NOW)
    assert r["decision"]=="HOLD" and r["stage"]=="EYES"

def test_uncertified_or_production_capability_never_executes():
    bad=Hands({"repo.prepare_pr":ActionAdapter("repo.prepare_pr",False,True,execute,verify)})
    r=bad.act(request())
    assert r["decision"]=="HOLD" and r["reason"]=="CAPABILITY_NOT_ELIGIBLE"

if __name__=="__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests: t()
    print(f"PASS {len(tests)} LOM Agentic OS P2 tests")
