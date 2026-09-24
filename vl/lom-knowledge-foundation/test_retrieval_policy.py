from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from retrieval_policy import KnowledgeRequest, retrieve_authoritative_context
from orchestrator_binding import bind_knowledge_to_objective


def record(**kw):
    d=dict(
        name="Source",
        domain="cadastral",
        jurisdiction="SABAH",
        source="official:test",
        provenance="test-fixture",
        authority_level="AUTHORITATIVE_OFFICIAL",
        version_or_date="2026-09-24",
        status="CURRENT",
        superseded_by=None,
        confidence=0.99,
        tags=["boundary"],
        location="fixture://source",
        claim_key="rule-1",
        content_digest="sha256:"+"a"*64,
    )
    d.update(kw)
    return d


def registry(rows):
    return {"records":rows}


def test_official_current_source_is_selected_before_lower_authority():
    rows=[
      record(),
      record(source="technical:test",authority_level="TECHNICAL_REFERENCE",confidence=1.0,content_digest="sha256:"+"b"*64),
    ]
    r=retrieve_authoritative_context(registry(rows),KnowledgeRequest("cadastral","SABAH",("boundary",)))
    assert r["decision"]=="ALLOW"
    assert r["authority_level"]=="AUTHORITATIVE_OFFICIAL"
    assert len(r["records"])==1
    assert r["records"][0]["source"]=="official:test"


def test_wrong_jurisdiction_fails_closed_for_consequential_request():
    r=retrieve_authoritative_context(registry([record(jurisdiction="SARAWAK")]),KnowledgeRequest("cadastral","SABAH"))
    assert r["decision"]=="HOLD"
    assert r["reason"]=="NO_APPLICABLE_KNOWLEDGE"


def test_low_confidence_fails_closed():
    r=retrieve_authoritative_context(registry([record(confidence=0.4)]),KnowledgeRequest("cadastral","SABAH"))
    assert r["decision"]=="HOLD"


def test_superseded_source_is_not_selected():
    r=retrieve_authoritative_context(registry([record(superseded_by="official:new")]),KnowledgeRequest("cadastral","SABAH"))
    assert r["decision"]=="HOLD"


def test_equal_top_authority_conflict_holds():
    rows=[
      record(source="official:a",content_digest="sha256:"+"a"*64),
      record(source="official:b",content_digest="sha256:"+"b"*64),
    ]
    r=retrieve_authoritative_context(registry(rows),KnowledgeRequest("cadastral","SABAH"))
    assert r["decision"]=="HOLD"
    assert r["reason"]=="SOURCE_CONFLICT"
    assert r["conflicts"]==["rule-1"]


def test_duplicate_is_flagged_not_deleted():
    one=record()
    two=record()
    r=retrieve_authoritative_context(registry([one,two]),KnowledgeRequest("cadastral","SABAH"))
    assert r["decision"]=="ALLOW"
    assert r["duplicate_groups"]


def test_binding_appends_knowledge_evidence_without_authority_change():
    base={"objective_id":"obj-1","evidence_refs":["evidence:input"],"requested_actions":["NON_PROD_CODE"]}
    r=bind_knowledge_to_objective(
      registry=registry([record()]),
      objective=base,
      domain="cadastral",
      jurisdiction="SABAH",
      tags=("boundary",),
    )
    assert r["decision"]=="ALLOW"
    assert r["authority_effect"]=="NONE"
    assert r["autonomous_ceiling"]=="PREPARE_PR"
    assert len(r["objective"]["evidence_refs"])==2


if __name__=="__main__":
    tests=[v for k,v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests: t()
    print(f"PASS {len(tests)} knowledge retrieval tests")
