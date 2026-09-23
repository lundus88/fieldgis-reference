from fact_truth import (
    AuthoritativeFactRegistry,
    FactClaim,
    build_fact_snapshot,
    resolve_fact,
)

NOW = 2_000_000_000


def claim(claim_id="c1", **overrides):
    data = dict(
        claim_id=claim_id,
        fact_key="company.registration_status",
        domain="LEGAL",
        value="IN_PROGRESS",
        source_class="HUMAN_CURRENT_CONFIRMATION",
        source_reference="human-confirmation:director",
        observed_at_epoch=NOW - 10,
        expires_at_epoch=NOW + 3600,
        supersedes=(),
        human_confirmed=True,
        independent=False,
    )
    data.update(overrides)
    return FactClaim(**data)


def test_consequential_current_human_fact_resolves():
    registry = AuthoritativeFactRegistry()
    registry.register(claim())
    result = resolve_fact(registry, "company.registration_status", now_epoch=NOW)
    assert result["status"] == "CURRENT"
    assert result["value"] == "IN_PROGRESS"
    assert result["human_confirmed"] is True
    assert result["production_authority"] == "HUMAN_ONLY"


def test_repository_assertion_cannot_silently_become_legal_truth():
    registry = AuthoritativeFactRegistry()
    registry.register(claim(
        source_class="REPOSITORY_ASSERTION",
        source_reference="repo:docs/business.json",
        value="ACTIVE",
        human_confirmed=False,
    ))
    result = resolve_fact(registry, "company.registration_status", now_epoch=NOW)
    assert result["status"] == "HOLD"
    assert result["reason"] == "CURRENT_HUMAN_CONFIRMATION_REQUIRED"


def test_new_human_claim_explicitly_supersedes_stale_repo_claim():
    registry = AuthoritativeFactRegistry()
    registry.register(claim(
        "repo-old",
        source_class="REPOSITORY_ASSERTION",
        source_reference="repo:docs/business.json",
        value="ACTIVE",
        observed_at_epoch=NOW - 1000,
        expires_at_epoch=NOW + 5000,
        human_confirmed=False,
    ))
    registry.register(claim(
        "human-new",
        value="IN_PROGRESS",
        supersedes=("repo-old",),
    ))
    result = resolve_fact(registry, "company.registration_status", now_epoch=NOW)
    assert result["status"] == "CURRENT"
    assert result["value"] == "IN_PROGRESS"
    assert result["selected_claim_id"] == "human-new"


def test_conflicting_unsuperseded_current_claims_hold():
    registry = AuthoritativeFactRegistry()
    registry.register(claim("a", value="ACTIVE"))
    registry.register(claim(
        "b",
        value="IN_PROGRESS",
        observed_at_epoch=NOW - 5,
        source_reference="human-confirmation:director:2",
    ))
    result = resolve_fact(registry, "company.registration_status", now_epoch=NOW)
    assert result["status"] == "HOLD"
    assert result["reason"] == "CONFLICTING_CURRENT_FACTS"


def test_stale_fact_holds():
    registry = AuthoritativeFactRegistry()
    registry.register(claim(expires_at_epoch=NOW - 1))
    result = resolve_fact(registry, "company.registration_status", now_epoch=NOW)
    assert result["status"] == "HOLD"
    assert result["reason"] == "FACT_EVIDENCE_STALE"


def test_future_claim_holds():
    registry = AuthoritativeFactRegistry()
    registry.register(claim(
        observed_at_epoch=NOW + 10,
        expires_at_epoch=NOW + 100,
    ))
    result = resolve_fact(registry, "company.registration_status", now_epoch=NOW)
    assert result["status"] == "HOLD"
    assert result["reason"] == "FUTURE_FACT_CLAIM"


def test_cross_fact_supersession_forbidden():
    registry = AuthoritativeFactRegistry()
    registry.register(claim("old"))
    try:
        registry.register(claim(
            "new",
            fact_key="company.account_status",
            supersedes=("old",),
        ))
        assert False, "expected cross-fact supersession rejection"
    except ValueError as exc:
        assert str(exc) == "CROSS_FACT_SUPERSESSION_FORBIDDEN"


def test_claim_id_collision_rejected():
    registry = AuthoritativeFactRegistry()
    registry.register(claim("same"))
    try:
        registry.register(claim("same", value="ACTIVE"))
        assert False, "expected collision"
    except ValueError as exc:
        assert str(exc) == "FACT_CLAIM_ID_COLLISION"


def test_registry_is_immutable():
    registry = AuthoritativeFactRegistry()
    try:
        registry.replace()
        assert False, "replace must be forbidden"
    except RuntimeError as exc:
        assert str(exc) == "IMMUTABLE_FACT_REGISTRY"
    try:
        registry.delete()
        assert False, "delete must be forbidden"
    except RuntimeError as exc:
        assert str(exc) == "IMMUTABLE_FACT_REGISTRY"


def test_nonconsequential_fact_can_resolve_without_human_confirmation():
    registry = AuthoritativeFactRegistry()
    registry.register(claim(
        fact_key="preview.commit_sha",
        domain="TECHNICAL",
        value="a" * 40,
        source_class="CONNECTED_SYSTEM_EVIDENCE",
        source_reference="vercel:deployment:123",
        human_confirmed=False,
    ))
    result = resolve_fact(registry, "preview.commit_sha", now_epoch=NOW)
    assert result["status"] == "CURRENT"
    assert result["value"] == "a" * 40


def test_same_value_multiple_sources_resolves_with_strongest_support():
    registry = AuthoritativeFactRegistry()
    registry.register(claim(
        "repo",
        fact_key="preview.commit_sha",
        domain="TECHNICAL",
        value="a" * 40,
        source_class="REPOSITORY_ASSERTION",
        source_reference="repo:preview.json",
        human_confirmed=False,
    ))
    registry.register(claim(
        "connected",
        fact_key="preview.commit_sha",
        domain="TECHNICAL",
        value="a" * 40,
        source_class="CONNECTED_SYSTEM_EVIDENCE",
        source_reference="vercel:deployment:123",
        observed_at_epoch=NOW - 5,
        human_confirmed=False,
        independent=True,
    ))
    result = resolve_fact(registry, "preview.commit_sha", now_epoch=NOW)
    assert result["status"] == "CURRENT"
    assert result["selected_claim_id"] == "connected"
    assert result["independent_support"] is True


def test_snapshot_holds_if_any_required_fact_is_unresolved():
    registry = AuthoritativeFactRegistry()
    registry.register(claim(
        fact_key="preview.commit_sha",
        domain="TECHNICAL",
        value="a" * 40,
        source_class="CONNECTED_SYSTEM_EVIDENCE",
        source_reference="vercel:deployment:123",
        human_confirmed=False,
    ))
    snapshot = build_fact_snapshot(
        registry,
        ["preview.commit_sha", "company.registration_status"],
        now_epoch=NOW,
    )
    assert snapshot["status"] == "HOLD"
    assert snapshot["execution_authority"] == "NONE"


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"PASS {len(tests)} Authoritative Fact Truth tests")
