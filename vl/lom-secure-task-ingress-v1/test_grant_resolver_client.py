from pathlib import Path
from tempfile import TemporaryDirectory

from grant_resolver_client import GrantResolverClient, GrantResolverConfig


def make_client(root: Path):
    key = root / "resolver.key"
    key.write_bytes(b"z" * 48)
    key.chmod(0o600)
    return GrantResolverClient(
        GrantResolverConfig(
            url="https://example.supabase.co/functions/v1/vrs-agent-grant-resolver",
            key_id="vps-query-v1",
            key_file=key,
            agent_id="lom-vps-runner",
        )
    )


def chain():
    return [
        {
            "grant_id": "11111111-1111-4111-8111-111111111111",
            "agent_id": "lom-vps-runner",
            "capabilities": ["factory.plan"],
            "scope": {"project_id": "lom-vps-validation", "target_environment": "staging"},
            "budget": {"timeout_seconds": 60, "max_retries": 0, "max_cost_minor": 0},
            "delegated_from_grant_id": "22222222-2222-4222-8222-222222222222",
            "valid_from": "2026-09-24T00:00:00Z",
            "valid_until": "2026-09-25T00:00:00Z",
            "revoked_at": None,
        },
        {
            "grant_id": "22222222-2222-4222-8222-222222222222",
            "agent_id": "lom-parent",
            "capabilities": ["factory.plan", "qa.execute"],
            "scope": {"project_id": "lom-vps-validation", "target_environment": "staging"},
            "budget": {"timeout_seconds": 120, "max_retries": 0, "max_cost_minor": 0},
            "delegated_from_grant_id": None,
            "valid_from": "2026-09-23T00:00:00Z",
            "valid_until": "2026-09-26T00:00:00Z",
            "revoked_at": None,
        },
    ]


def response(rows=None):
    return {
        "schema": "lom.acp-grant-chain-response/1",
        "grant_ref": "acp-grant:11111111-1111-4111-8111-111111111111",
        "agent_id": "lom-vps-runner",
        "project_id": "lom-vps-validation",
        "target_environment": "staging",
        "observed_at_epoch": 1790265600,
        "rows": chain() if rows is None else rows,
        "production": False,
        "production_locked": True,
    }


def test_valid_chain_resolves_locally():
    with TemporaryDirectory() as tmp:
        client = make_client(Path(tmp))
        grant = client.validate_response(
            response(),
            grant_ref=response()["grant_ref"],
            project_id="lom-vps-validation",
            target_environment="staging",
            now_epoch=1790265600,
        )
        assert grant["grant_id"] == "11111111-1111-4111-8111-111111111111"
        assert grant["capabilities"] == ["factory.plan"]


def test_revoked_leaf_fails_closed():
    with TemporaryDirectory() as tmp:
        client = make_client(Path(tmp))
        rows = chain()
        rows[0]["revoked_at"] = "2026-09-24T01:00:00Z"
        try:
            client.validate_response(
                response(rows),
                grant_ref=response()["grant_ref"],
                project_id="lom-vps-validation",
                target_environment="staging",
                now_epoch=1790265600,
            )
        except Exception as exc:
            assert "DENY_POLICY_UNAVAILABLE" in str(exc)
        else:
            raise AssertionError("revoked grant unexpectedly accepted")


def test_widened_child_capability_fails_closed():
    with TemporaryDirectory() as tmp:
        client = make_client(Path(tmp))
        rows = chain()
        rows[0]["capabilities"] = ["factory.plan", "release.request_approval"]
        try:
            client.validate_response(
                response(rows),
                grant_ref=response()["grant_ref"],
                project_id="lom-vps-validation",
                target_environment="staging",
                now_epoch=1790265600,
            )
        except Exception as exc:
            assert "DENY_DELEGATION_ESCALATION" in str(exc)
        else:
            raise AssertionError("widened grant unexpectedly accepted")


def test_project_mismatch_fails_closed():
    with TemporaryDirectory() as tmp:
        client = make_client(Path(tmp))
        bad = response()
        bad["project_id"] = "other-project"
        try:
            client.validate_response(
                bad,
                grant_ref=response()["grant_ref"],
                project_id="lom-vps-validation",
                target_environment="staging",
                now_epoch=1790265600,
            )
        except RuntimeError as exc:
            assert str(exc) == "GRANT_RESOLVER_PROJECT_MISMATCH"
        else:
            raise AssertionError("project mismatch unexpectedly accepted")


def test_stale_response_fails_closed():
    with TemporaryDirectory() as tmp:
        client = make_client(Path(tmp))
        try:
            client.validate_response(
                response(),
                grant_ref=response()["grant_ref"],
                project_id="lom-vps-validation",
                target_environment="staging",
                now_epoch=1790266000,
            )
        except RuntimeError as exc:
            assert str(exc) == "GRANT_RESOLVER_RESPONSE_STALE"
        else:
            raise AssertionError("stale response unexpectedly accepted")


def test_public_or_http_resolver_url_is_rejected():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        key = root / "resolver.key"
        key.write_bytes(b"z" * 48)
        key.chmod(0o600)
        try:
            GrantResolverClient(
                GrantResolverConfig(
                    url="http://example.supabase.co/functions/v1/vrs-agent-grant-resolver",
                    key_id="vps-query-v1",
                    key_file=key,
                    agent_id="lom-vps-runner",
                )
            )
        except RuntimeError as exc:
            assert str(exc) == "GRANT_RESOLVER_URL_INVALID"
        else:
            raise AssertionError("http resolver unexpectedly allowed")


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} ACP grant resolver client tests")
