#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

VALID_TARGETS = {
    "REJECT",
    "KNOWLEDGE_ONLY",
    "UPGRADE_EXISTING_CAPABILITY",
    "ADD_DOMAIN_CAPABILITY",
    "ADD_ADAPTER",
    "ADD_TEMPLATE",
    "ADD_SHARED_ENGINE",
    "ADD_NEW_MODULE",
}

@dataclass(frozen=True)
class Candidate:
    name: str
    evidence_present: bool
    duplicate_capability_exists: bool
    external_integration_only: bool
    domain_subset: bool
    reusable_pattern: bool
    cross_domain_shared_logic: bool
    distinct_domain_rules: bool
    distinct_lifecycle: bool
    distinct_data: bool
    runtime_change: bool
    rollback_defined: bool
    owner_identified: bool
    architecture_target_identified: bool
    risk_assessed: bool

@dataclass(frozen=True)
class Decision:
    disposition: str
    reasons: tuple[str, ...]
    human_gate_required: bool

def evaluate(c: Candidate) -> Decision:
    missing = []
    if not c.evidence_present:
        missing.append("evidence_missing")
    if not c.owner_identified:
        missing.append("owner_missing")
    if not c.architecture_target_identified:
        missing.append("architecture_target_missing")
    if not c.risk_assessed:
        missing.append("risk_not_assessed")
    if c.runtime_change and not c.rollback_defined:
        missing.append("rollback_missing")

    if missing:
        return Decision("REJECT", tuple(missing), True)

    if c.duplicate_capability_exists:
        return Decision(
            "UPGRADE_EXISTING_CAPABILITY",
            ("existing_authoritative_capability_detected", "reuse_before_build"),
            True,
        )

    if c.external_integration_only:
        return Decision("ADD_ADAPTER", ("external_service_boundary_only",), True)

    if c.domain_subset:
        return Decision("ADD_DOMAIN_CAPABILITY", ("belongs_inside_existing_domain_system",), True)

    if c.reusable_pattern and not c.cross_domain_shared_logic:
        return Decision("ADD_TEMPLATE", ("reusable_pattern_without_independent_runtime",), True)

    if c.cross_domain_shared_logic:
        return Decision("ADD_SHARED_ENGINE", ("cross_domain_reusable_logic",), True)

    if c.distinct_domain_rules and c.distinct_lifecycle and c.distinct_data:
        return Decision("ADD_NEW_MODULE", ("proven_independent_domain_boundary",), True)

    return Decision("KNOWLEDGE_ONLY", ("valuable_but_no_runtime_boundary_proven",), False)

def validate_dispositions(values: Iterable[str]) -> bool:
    return all(v in VALID_TARGETS for v in values)
