from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Any

from secure_task_ingress import SecureTaskIngress

DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_HTTP_BODY = 131072


def _load_key(path: Path) -> bytes:
    st = path.stat()
    if st.st_mode & 0o077:
        raise RuntimeError("INGRESS_KEY_FILE_PERMISSIONS_TOO_BROAD")
    secret = path.read_bytes().strip()
    if len(secret) < 32:
        raise RuntimeError("INGRESS_KEY_TOO_SHORT")
    return secret


def build_ingress_from_env(env: dict[str, str] | None = None) -> tuple[SecureTaskIngress, str, int]:
    env = dict(os.environ if env is None else env)
    bind = env.get("LOM_INGRESS_BIND", DEFAULT_BIND)
    if bind != DEFAULT_BIND:
        raise RuntimeError("INGRESS_BIND_MUST_BE_LOOPBACK_P0")

    try:
        port = int(env.get("LOM_INGRESS_PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise RuntimeError("INGRESS_PORT_INVALID") from exc
    if port < 1024 or port > 65535:
        raise RuntimeError("INGRESS_PORT_INVALID")

    db_path = Path(env.get("LOM_INGRESS_DB", "/home/lom-runner/lom-runtime/secure-ingress.db"))
    key_path = Path(env.get("LOM_INGRESS_KEY_FILE", "/home/lom-runner/.config/lom/ingress-hmac.key"))
    key_id = env.get("LOM_INGRESS_KEY_ID", "vps-local-v1")
    secret = _load_key(key_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ingress = SecureTaskIngress(
        store_path=db_path,
        signing_keys={key_id: secret},
        max_queue=64,
        max_ttl_seconds=900,
        max_envelope_bytes=65536,
        max_submissions_per_minute=30,
        max_attempts=3,
    )
    return ingress, bind, port


def handler_for(ingress: SecureTaskIngress):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LOMSecureIngress/1"

        def _send(self, status: int, body: dict[str, Any]) -> None:
            raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:
            if self.path != "/health":
                self._send(404, {"status": "NOT_FOUND"})
                return
            status = ingress.status()
            self._send(200, {
                "status": "READY" if status["audit_chain"]["status"] == "READY" else "HOLD",
                "production": False,
                "production_locked": True,
                "queue_depth": status["queue_depth"],
                "audit_chain": status["audit_chain"],
            })

        def do_POST(self) -> None:
            if self.path != "/v1/tasks":
                self._send(404, {"status": "NOT_FOUND"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send(400, {"decision": "HOLD", "reason": "CONTENT_LENGTH_INVALID"})
                return
            if length <= 0 or length > MAX_HTTP_BODY:
                self._send(413, {"decision": "HOLD", "reason": "HTTP_BODY_BOUND_EXCEEDED"})
                return
            try:
                body = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(400, {"decision": "HOLD", "reason": "HTTP_JSON_INVALID"})
                return
            if not isinstance(body, dict) or set(body) != {"envelope", "signature"}:
                self._send(400, {"decision": "HOLD", "reason": "HTTP_FIELDS_INVALID"})
                return
            result = ingress.submit(body["envelope"], body["signature"])
            code = 202 if result.get("decision") in {"ACCEPTED", "ACCEPTED_IDEMPOTENT"} else 403
            self._send(code, result)

        def log_message(self, fmt: str, *args: Any) -> None:
            print("lom-secure-ingress:", fmt % args, flush=True)

    return Handler


def main() -> None:
    ingress, bind, port = build_ingress_from_env()
    server = ThreadingHTTPServer((bind, port), handler_for(ingress))
    print(f"lom-secure-ingress READY http://{bind}:{port} production_locked=true", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        ingress.close()


if __name__ == "__main__":
    main()
