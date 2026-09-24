from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

AUTHORITY_RANK = {
    "AUTHORITATIVE_OFFICIAL": 60,
    "PROFESSIONAL_REFERENCE": 50,
    "TECHNICAL_REFERENCE": 40,
    "PROJECT_EVIDENCE": 30,
    "GENERATED_MATERIAL": 20,
    "ARCHIVE": 10,
}
CURRENT_STATUS = {"CURRENT", "ACTIVE", "VALID"}
DEFAULT_MIN_CONFIDENCE = 0.80


def _digest(value: Any) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":")).encode("utf-8")
    return "sha256:"+sha256(raw).hexdigest()


@dataclass(frozen=True)
class KnowledgeRequest:
    domain: str
    jurisdiction: str
    tags: tuple[str, ...] = ()
    consequential: bool = True
    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    allow_global_fallback: bool = True


def _matches_jurisdiction(record: dict[str, Any], req: KnowledgeRequest) -> bool:
    actual=str(record.get("jurisdiction") or "").strip().upper()
    wanted=req.jurisdiction.strip().upper()
    return actual == wanted or (req.allow_global_fallback and actual == "GLOBAL")


def _record_identity(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record.get("source"),
        record.get("version_or_date"),
        record.get("location"),
        record.get("content_digest"),
    )


def retrieve_authoritative_context(
    registry: dict[str, Any],
    request: KnowledgeRequest,
) -> dict[str, Any]:
    if not request.domain.strip() or not request.jurisdiction.strip():
        return {"decision":"HOLD","reason":"DOMAIN_OR_JURISDICTION_REQUIRED","records":[]}
    if not 0 <= request.min_confidence <= 1:
        return {"decision":"HOLD","reason":"CONFIDENCE_THRESHOLD_INVALID","records":[]}

    records=registry.get("records")
    if not isinstance(records,list):
        return {"decision":"HOLD","reason":"KNOWLEDGE_REGISTRY_INVALID","records":[]}

    eligible=[]
    rejected=[]
    wanted_tags={x.strip().lower() for x in request.tags if x.strip()}
    for row in records:
        if not isinstance(row,dict):
            rejected.append({"reason":"INVALID_RECORD"})
            continue
        if str(row.get("domain") or "").strip().lower() != request.domain.strip().lower():
            continue
        if not _matches_jurisdiction(row,request):
            continue
        status=str(row.get("status") or "").strip().upper()
        if status not in CURRENT_STATUS or row.get("superseded_by"):
            rejected.append({"source":row.get("source"),"reason":"STALE_OR_SUPERSEDED"})
            continue
        authority=str(row.get("authority_level") or "")
        if authority not in AUTHORITY_RANK:
            rejected.append({"source":row.get("source"),"reason":"UNKNOWN_AUTHORITY"})
            continue
        confidence=row.get("confidence")
        if not isinstance(confidence,(int,float)) or confidence < request.min_confidence:
            rejected.append({"source":row.get("source"),"reason":"LOW_CONFIDENCE"})
            continue
        tags={str(x).strip().lower() for x in (row.get("tags") or [])}
        if wanted_tags and not wanted_tags.intersection(tags):
            continue
        eligible.append(dict(row))

    if not eligible:
        reason="NO_APPLICABLE_KNOWLEDGE" if request.consequential else "NO_CONTEXT"
        return {"decision":"HOLD" if request.consequential else "ALLOW","reason":reason,"records":[],"rejected":rejected}

    seen={}
    duplicate_groups=[]
    for row in eligible:
        identity=_record_identity(row)
        if identity in seen:
            duplicate_groups.append([seen[identity].get("source"),row.get("source")])
        else:
            seen[identity]=row

    eligible.sort(
        key=lambda r:(
            AUTHORITY_RANK[r["authority_level"]],
            float(r["confidence"]),
            str(r.get("version_or_date") or ""),
        ),
        reverse=True,
    )
    top_rank=AUTHORITY_RANK[eligible[0]["authority_level"]]
    top=[r for r in eligible if AUTHORITY_RANK[r["authority_level"]] == top_rank]

    claims={}
    for row in top:
        claim=row.get("claim_key")
        digest=row.get("content_digest")
        if claim and digest:
            claims.setdefault(str(claim),set()).add(str(digest))
    conflicts=sorted(claim for claim,digests in claims.items() if len(digests)>1)
    if conflicts:
        return {
            "decision":"HOLD",
            "reason":"SOURCE_CONFLICT",
            "conflicts":conflicts,
            "records":top,
            "duplicate_groups":duplicate_groups,
            "rejected":rejected,
        }

    selected=top
    evidence_refs=[
        f"knowledge:{_digest({'source':r.get('source'),'version':r.get('version_or_date'),'location':r.get('location')})}"
        for r in selected
    ]
    return {
        "decision":"ALLOW",
        "reason":"AUTHORITATIVE_CONTEXT_SELECTED",
        "domain":request.domain,
        "jurisdiction":request.jurisdiction,
        "records":selected,
        "evidence_refs":evidence_refs,
        "authority_level":selected[0]["authority_level"],
        "duplicate_groups":duplicate_groups,
        "rejected":rejected,
        "selection_explanation":{
            "filter_order":["domain","jurisdiction","status","supersession","authority","confidence","tags"],
            "semantic_similarity_authority":"DOWNSTREAM_ONLY",
            "top_authority_rank":top_rank,
            "fail_closed_on_conflict":True,
        },
        "context_digest":_digest(selected),
    }
