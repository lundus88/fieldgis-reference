from __future__ import annotations

from typing import Any
from retrieval_policy import KnowledgeRequest, retrieve_authoritative_context


def bind_knowledge_to_objective(
    *,
    registry: dict[str, Any],
    objective: dict[str, Any],
    domain: str,
    jurisdiction: str,
    tags: tuple[str, ...] = (),
    consequential: bool = True,
) -> dict[str, Any]:
    """Prepare an evidence-bound objective for the existing Gate E orchestrator.

    This adapter grants no authority and performs no execution. It only appends
    authoritative knowledge evidence after the Knowledge Registry policy passes.
    """
    knowledge=retrieve_authoritative_context(
        registry,
        KnowledgeRequest(
            domain=domain,
            jurisdiction=jurisdiction,
            tags=tags,
            consequential=consequential,
        ),
    )
    if knowledge["decision"] != "ALLOW":
        return {
            "decision":"HOLD",
            "reason":knowledge["reason"],
            "knowledge":knowledge,
            "objective":None,
            "authority_effect":"NONE",
        }

    existing=list(objective.get("evidence_refs") or [])
    combined=list(dict.fromkeys(existing + list(knowledge.get("evidence_refs") or [])))
    if not combined:
        return {
            "decision":"HOLD",
            "reason":"MISSING_CRITICAL_EVIDENCE",
            "knowledge":knowledge,
            "objective":None,
            "authority_effect":"NONE",
        }

    bound=dict(objective)
    bound["evidence_refs"]=combined
    bound["knowledge_context_digest"]=knowledge["context_digest"]
    bound["knowledge_authority_level"]=knowledge["authority_level"]
    bound["knowledge_domain"]=domain
    bound["knowledge_jurisdiction"]=jurisdiction
    return {
        "decision":"ALLOW",
        "reason":"KNOWLEDGE_BOUND_OBJECTIVE_READY",
        "knowledge":knowledge,
        "objective":bound,
        "authority_effect":"NONE",
        "autonomous_ceiling":"PREPARE_PR",
        "production_authority":"HUMAN_ONLY",
    }
