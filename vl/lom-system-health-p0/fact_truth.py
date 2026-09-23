from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Any, Iterable

FACT_SCHEMA = "lom.authoritative-fact/1"
RESOLUTION_SCHEMA = "lom.fact-resolution/1"

SOURCE_CLASSES = {
    "HUMAN_CURRENT_CONFIRMATION",
    "OFFICIAL_DOCUMENT",
    "CONNECTED_SYSTEM_EVIDENCE",
    "REPOSITORY_ASSERTION",
    "INTERNAL_NOTE",
}

CONSEQUENTIAL_DOMAINS = {
    "LEGAL",
    "FINANCIAL",
    "PRODUCTION",
    "CUSTOMER_COMMITMENT",
    "SECURITY_AUTHORITY",
}

SOURCE_WEIGHT = {
    "HUMAN_CURRENT_CONFIRMATION": 100,
    "OFFICIAL_DOCUMENT": 90,
    "CONNECTED_SYSTEM_EVIDENCE": 80,
    "REPOSITORY_ASSERTION": 50,
    "INTERNAL_NOTE": 20,
}


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class FactClaim:
    claim_id: str
    fact_key: str
    domain: str
    value: Any
    source_class: str
    source_reference: str
    observed_at_epoch: int
    expires_at_epoch: int
    supersedes: tuple[str, ...] = ()
    human_confirmed: bool = False
    independent: bool = False

    @property
    def value_digest(self) -> str:
        return digest(self.value)


class AuthoritativeFactRegistry:
    """Immutable claim registry with explicit supersession.

    It never silently overwrites older claims. Resolution either selects one
    current, defensible claim or fails closed.
    """

    def __init__(self) -> None:
        self._claims: dict[str, FactClaim] = {}
        self._digests: dict[str, str] = {}

    def register(self, claim: FactClaim) -> FactClaim:
        if not claim.claim_id or not claim.fact_key or not claim.source_reference:
            raise ValueError("FACT_IDENTITY_REQUIRED")
        if claim.source_class not in SOURCE_CLASSES:
            raise ValueError("UNKNOWN_SOURCE_CLASS")
        if claim.observed_at_epoch <= 0 or claim.expires_at_epoch < claim.observed_at_epoch:
            raise ValueError("FACT_TIME_INVALID")
        if claim.claim_id in claim.supersedes:
            raise ValueError("FACT_SELF_SUPERSESSION")

        body = asdict(claim)
        claim_digest = digest(body)
        existing = self._digests.get(claim.claim_id)
        if existing is not None and existing != claim_digest:
            raise ValueError("FACT_CLAIM_ID_COLLISION")

        for old_id in claim.supersedes:
            old = self._claims.get(old_id)
            if old is None:
                raise ValueError("SUPERSEDED_CLAIM_NOT_REGISTERED")
            if old.fact_key != claim.fact_key:
                raise ValueError("CROSS_FACT_SUPERSESSION_FORBIDDEN")
            if old.observed_at_epoch > claim.observed_at_epoch:
                raise ValueError("SUPERSESSION_TIME_REVERSAL")

        self._claims.setdefault(claim.claim_id, claim)
        self._digests.setdefault(claim.claim_id, claim_digest)
        self._assert_acyclic(claim.fact_key)
        return self._claims[claim.claim_id]

    def _assert_acyclic(self, fact_key: str) -> None:
        graph = {
            claim.claim_id: set(claim.supersedes)
            for claim in self._claims.values()
            if claim.fact_key == fact_key
        }
        visiting: set[str] = set()
        visited: set[str] = set()

        def walk(node: str) -> None:
            if node in visiting:
                raise ValueError("FACT_SUPERSESSION_CYCLE")
            if node in visited:
                return
            visiting.add(node)
            for parent in graph.get(node, set()):
                if parent in graph:
                    walk(parent)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            walk(node)

    def claims_for(self, fact_key: str) -> list[FactClaim]:
        return sorted(
            [claim for claim in self._claims.values() if claim.fact_key == fact_key],
            key=lambda item: (item.observed_at_epoch, item.claim_id),
        )

    def replace(self, *_args, **_kwargs) -> None:
        raise RuntimeError("IMMUTABLE_FACT_REGISTRY")

    def delete(self, *_args, **_kwargs) -> None:
        raise RuntimeError("IMMUTABLE_FACT_REGISTRY")


def resolve_fact(
    registry: AuthoritativeFactRegistry,
    fact_key: str,
    *,
    now_epoch: int,
    consequential_domains: Iterable[str] = CONSEQUENTIAL_DOMAINS,
) -> dict[str, Any]:
    claims = registry.claims_for(fact_key)
    if not claims:
        return _hold(fact_key, "FACT_NOT_REGISTERED")

    if now_epoch <= 0:
        return _hold(fact_key, "RESOLUTION_TIME_INVALID")

    for claim in claims:
        if claim.observed_at_epoch > now_epoch:
            return _hold(fact_key, "FUTURE_FACT_CLAIM")

    superseded_ids = {old_id for claim in claims for old_id in claim.supersedes}
    active = [claim for claim in claims if claim.claim_id not in superseded_ids]

    fresh = [claim for claim in active if claim.expires_at_epoch >= now_epoch]
    if not fresh:
        return _hold(fact_key, "FACT_EVIDENCE_STALE", claims=active)

    domains = {claim.domain for claim in fresh}
    if len(domains) != 1:
        return _hold(fact_key, "FACT_DOMAIN_CONFLICT", claims=fresh)
    domain = next(iter(domains))

    # Different current values are a hard conflict unless explicit
    # supersession reduced them to one active value.
    value_digests = {claim.value_digest for claim in fresh}
    if len(value_digests) > 1:
        return _hold(fact_key, "CONFLICTING_CURRENT_FACTS", claims=fresh)

    # Same value from multiple sources is acceptable; choose the strongest,
    # then newest, while preserving all supporting claims.
    selected = max(
        fresh,
        key=lambda claim: (
            SOURCE_WEIGHT[claim.source_class],
            claim.observed_at_epoch,
            claim.claim_id,
        ),
    )

    consequential = domain in set(consequential_domains)
    if consequential:
        current_human = any(
            claim.human_confirmed and claim.source_class == "HUMAN_CURRENT_CONFIRMATION"
            for claim in fresh
        )
        official_or_connected = any(
            claim.source_class in {"OFFICIAL_DOCUMENT", "CONNECTED_SYSTEM_EVIDENCE"}
            for claim in fresh
        )

        # Consequential facts may be supported by an official/connected source,
        # but current human confirmation is required before LOM treats the
        # resolution as actionable truth. This prevents stale repository text
        # from silently becoming legal/financial/Production authority.
        if not current_human:
            return _hold(
                fact_key,
                "CURRENT_HUMAN_CONFIRMATION_REQUIRED",
                claims=fresh,
                domain=domain,
                official_or_connected=official_or_connected,
            )

    body = {
        "schema": RESOLUTION_SCHEMA,
        "fact_key": fact_key,
        "domain": domain,
        "status": "CURRENT",
        "value": selected.value,
        "value_digest": selected.value_digest,
        "selected_claim_id": selected.claim_id,
        "supporting_claim_ids": sorted(claim.claim_id for claim in fresh),
        "source_class": selected.source_class,
        "source_reference": selected.source_reference,
        "observed_at_epoch": selected.observed_at_epoch,
        "expires_at_epoch": min(claim.expires_at_epoch for claim in fresh),
        "consequential": consequential,
        "human_confirmed": any(claim.human_confirmed for claim in fresh),
        "independent_support": any(claim.independent for claim in fresh),
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "fact_mutation_authority": "NONE",
    }
    return {**body, "resolution_digest": digest(body)}


def _hold(
    fact_key: str,
    reason: str,
    *,
    claims: Iterable[FactClaim] = (),
    domain: str | None = None,
    official_or_connected: bool | None = None,
) -> dict[str, Any]:
    body = {
        "schema": RESOLUTION_SCHEMA,
        "fact_key": fact_key or None,
        "domain": domain,
        "status": "HOLD",
        "reason": reason,
        "claim_ids": sorted(claim.claim_id for claim in claims),
        "official_or_connected_support": official_or_connected,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "fact_mutation_authority": "NONE",
    }
    return {**body, "resolution_digest": digest(body)}


def build_fact_snapshot(
    registry: AuthoritativeFactRegistry,
    fact_keys: Iterable[str],
    *,
    now_epoch: int,
) -> dict[str, Any]:
    keys = sorted({str(key).strip() for key in fact_keys if str(key).strip()})
    if not keys:
        body = {
            "schema": "lom.fact-snapshot/1",
            "status": "HOLD",
            "reason": "FACT_KEYS_REQUIRED",
            "facts": [],
            "autonomous_ceiling": "PREPARE_PR",
            "production_authority": "HUMAN_ONLY",
        }
        return {**body, "snapshot_digest": digest(body)}

    facts = [resolve_fact(registry, key, now_epoch=now_epoch) for key in keys]
    overall = "CURRENT"
    if any(item["status"] == "HOLD" for item in facts):
        overall = "HOLD"

    body = {
        "schema": "lom.fact-snapshot/1",
        "status": overall,
        "facts": facts,
        "autonomous_ceiling": "PREPARE_PR",
        "production_authority": "HUMAN_ONLY",
        "protected_main_merge": "HUMAN_ONLY",
        "execution_authority": "NONE",
    }
    return {**body, "snapshot_digest": digest(body)}
