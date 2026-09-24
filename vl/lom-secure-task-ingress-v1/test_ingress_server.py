from pathlib import Path
from tempfile import TemporaryDirectory

from ingress_server import build_ingress_from_env


def base_env(root: Path):
    key = root / "ingress-hmac.key"
    key.write_bytes(b"x" * 48)
    key.chmod(0o600)
    return {
        "LOM_INGRESS_BIND": "127.0.0.1",
        "LOM_INGRESS_PORT": "8765",
        "LOM_INGRESS_DB": str(root / "runtime" / "ingress.db"),
        "LOM_INGRESS_KEY_FILE": str(key),
        "LOM_INGRESS_KEY_ID": "test-v1",
    }


def test_loopback_configuration_ready():
    with TemporaryDirectory() as tmp:
        env = base_env(Path(tmp))
        ingress, bind, port = build_ingress_from_env(env)
        assert bind == "127.0.0.1"
        assert port == 8765
        assert ingress.status()["production_locked"] is True
        assert ingress.status()["connector_execution"] == "FORBIDDEN"
        ingress.close()


def test_public_bind_fails_closed():
    with TemporaryDirectory() as tmp:
        env = base_env(Path(tmp))
        env["LOM_INGRESS_BIND"] = "0.0.0.0"
        try:
            build_ingress_from_env(env)
        except RuntimeError as exc:
            assert str(exc) == "INGRESS_BIND_MUST_BE_LOOPBACK_P0"
        else:
            raise AssertionError("public bind unexpectedly allowed")


def test_broad_secret_permissions_fail_closed():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = base_env(root)
        Path(env["LOM_INGRESS_KEY_FILE"]).chmod(0o644)
        try:
            build_ingress_from_env(env)
        except RuntimeError as exc:
            assert str(exc) == "INGRESS_KEY_FILE_PERMISSIONS_TOO_BROAD"
        else:
            raise AssertionError("broad secret permissions unexpectedly allowed")


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} private ingress deployment tests")
