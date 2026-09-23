from job_command_center import compose_job_view, evaluate_event

def test_composed_job_view():
    r = compose_job_view(
        job_id="LD-JOB-001",
        org_id="ORG-001",
        customer_ref="CUS-001",
        current_state="PAYMENT",
        evidence={
            "commercial_status":"APPROVED",
            "payment_status":"RECONCILED",
            "production_status":"NOT_STARTED",
            "evidence_freshness":"CURRENT",
        },
    )
    assert r["decision"] == "PASS"
    assert r["next_action"] == "EVALUATE_PRODUCTION"
    assert len(r["view_digest"]) == 64

def test_illegal_transition_holds():
    r = evaluate_event(
        current_state="LEAD",
        proposed_state="PAYMENT",
        event_id="evt-1",
        signed=True,
        idempotency_key="k-1",
        consumed_keys=set(),
        evidence_refs=["e:lead"],
    )
    assert r["decision"] == "HOLD"
    assert r["reason"] == "ILLEGAL_TRANSITION"

def test_unsigned_event_holds():
    r = evaluate_event(
        current_state="LEAD",
        proposed_state="DISCOVERY",
        event_id="evt-2",
        signed=False,
        idempotency_key="k-2",
        consumed_keys=set(),
        evidence_refs=["e:lead"],
    )
    assert r["reason"] == "UNVERIFIED_EVENT"

def test_replay_is_idempotent():
    r = evaluate_event(
        current_state="LEAD",
        proposed_state="DISCOVERY",
        event_id="evt-3",
        signed=True,
        idempotency_key="k-3",
        consumed_keys={"k-3"},
        evidence_refs=["e:lead"],
    )
    assert r["decision"] == "IDEMPOTENT_REPLAY"

def test_production_requires_separate_authority():
    r = evaluate_event(
        current_state="PAYMENT",
        proposed_state="PRODUCTION",
        event_id="evt-4",
        signed=True,
        idempotency_key="k-4",
        consumed_keys=set(),
        evidence_refs=["e:payment"],
        authorities={"production_authority":False},
    )
    assert r["decision"] == "HOLD"
    assert r["reason"] == "HUMAN_AUTHORITY_REQUIRED"

def test_valid_signed_transition_passes_without_production_authority():
    r = evaluate_event(
        current_state="LEAD",
        proposed_state="DISCOVERY",
        event_id="evt-5",
        signed=True,
        idempotency_key="k-5",
        consumed_keys=set(),
        evidence_refs=["e:lead"],
    )
    assert r["decision"] == "PASS"
    assert r["production_activation_authorized"] is False
    assert len(r["receipt_digest"]) == 64

if __name__ == "__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests: t()
    print(f"PASS {len(tests)} LD Unified Job Command Center tests")
