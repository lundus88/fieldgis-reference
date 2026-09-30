import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen

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


def test_health_endpoint_uses_sqlite_on_server_thread():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        env = base_env(root)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env["LOM_INGRESS_PORT"] = str(port)

        child_env = os.environ.copy()
        child_env.update(env)
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("ingress_server.py"))],
            cwd=Path(__file__).parent,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            deadline = time.time() + 5
            last_error = None
            while time.time() < deadline:
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as response:
                        body = json.loads(response.read().decode("utf-8"))
                    assert response.status == 200
                    assert body["status"] == "READY"
                    assert body["production"] is False
                    assert body["production_locked"] is True
                    break
                except Exception as exc:
                    last_error = exc
                    time.sleep(0.1)
            else:
                output = proc.stdout.read() if proc.stdout else ""
                raise AssertionError(f"health endpoint failed: {last_error}\n{output}")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
    print(f"PASS {len(tests)} private ingress deployment tests")
