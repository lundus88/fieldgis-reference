from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import importlib.util
import json
from pathlib import Path
import secrets
import stat
import sys
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "lom.acp-grant-query/1"
RESPONSE_SCHEMA = "lom.acp-grant-chain-response/1"
MAX_RESPONSE_BYTES = 65536


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _load_grant_resolution():
    path = ROOT / "agent-control-plane" / "grant_resolution.py"
    spec = importlib.util.spec_from_file_location("lom_acp_grant_resolution", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("ACP_GRANT_RESOLUTION_LOAD_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_secret(path: Path) -> bytes:
    st = path.stat()
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise RuntimeError("GRANT_RESOLVER_KEY_FILE_PERMISSIONS_TOO_BROAD")
    secret = path.read_bytes().strip()
    if len(secret) < 32:
        raise RuntimeError("GRANT_RESOLVER_KEY_TOO_SHORT")
    return secret


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise RuntimeError("GRANT_RESOLVER_URL_INVALID")
    if parsed.query or parsed.fragment:
        raise RuntimeError("GRANT_RESOLVER_URL_INVALID")
    if not parsed.path.endswith("/functions/v1/vrs-agent-grant-resolver"):
        raise RuntimeError("GRANT_RESOLVER_PATH_INVALID")
    return url


@dataclass(frozen=True)
class GrantResolverConfig:
    url: str
    key_id: str
    key_file: Path
    agent_id: str
    max_clock_skew_seconds: int = 90


class GrantResolverClient:
    def __init__(self, config: GrantResolverConfig) -> None:
        if not config.key_id or len(config.key_id) > 80:
            raise RuntimeError("GRANT_RESOLVER_KEY_ID_INVALID")
        if not config.agent_id or len(config.agent_id) > 128:
            raise RuntimeError("GRANT_RESOLVER_AGENT_ID_INVALID")
        if config.max_clock_skew_seconds < 30 or config.max_clock_skew_seconds > 300:
            raise RuntimeError("GRANT_RESOLVER_CLOCK_BOUND_INVALID")
        self.config = GrantResolverConfig(
            url=_validate_url(config.url),
            key_id=config.key_id,
            key_file=config.key_file,
            agent_id=config.agent_id,
            max_clock_skew_seconds=config.max_clock_skew_seconds,
        )
        self.secret = _load_secret(config.key_file)
        self.grant_resolution = _load_grant_resolution()

    def _build_query(
        self,
        *,
        grant_ref: str,
        project_id: str,
        target_environment: str,
        now_epoch: int,
    ) -> dict[str, Any]:
        if not grant_ref.startswith("acp-grant:") or len(grant_ref) > 220:
            raise RuntimeError("GRANT_REF_INVALID")
        if not project_id or len(project_id) > 200:
            raise RuntimeError("PROJECT_ID_INVALID")
        if target_environment not in {"development", "staging"}:
            raise RuntimeError("NON_PRODUCTION_SCOPE_REQUIRED")
        return {
            "schema": SCHEMA,
            "grant_ref": grant_ref,
            "agent_id": self.config.agent_id,
            "project_id": project_id,
            "target_environment": target_environment,
            "issued_at_epoch": now_epoch,
            "nonce": secrets.token_hex(16),
        }

    def _signature(self, body: dict[str, Any]) -> str:
        return "hmac-sha256:" + hmac.new(self.secret, canonical_bytes(body), sha256).hexdigest()

    def resolve(
        self,
        *,
        grant_ref: str,
        project_id: str,
        target_environment: str,
        now_epoch: int | None = None,
        timeout_seconds: float = 5.0,
    ) -> dict[str, Any]:
        now_epoch = int(time.time()) if now_epoch is None else int(now_epoch)
        body = self._build_query(
            grant_ref=grant_ref,
            project_id=project_id,
            target_environment=target_environment,
            now_epoch=now_epoch,
        )
        request = Request(
            self.config.url,
            data=canonical_bytes(body),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-LOM-Key-Id": self.config.key_id,
                "X-LOM-Signature": self._signature(body),
            },
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("GRANT_RESOLVER_RESPONSE_TOO_LARGE")
            if response.status != 200:
                raise RuntimeError("GRANT_RESOLVER_HTTP_REJECTED")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GRANT_RESOLVER_JSON_INVALID") from exc
        return self.validate_response(
            payload,
            grant_ref=grant_ref,
            project_id=project_id,
            target_environment=target_environment,
            now_epoch=now_epoch,
        )

    def validate_response(
        self,
        payload: Any,
        *,
        grant_ref: str,
        project_id: str,
        target_environment: str,
        now_epoch: int,
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise RuntimeError("GRANT_RESOLVER_RESPONSE_INVALID")
        if payload.get("schema") != RESPONSE_SCHEMA:
            raise RuntimeError("GRANT_RESOLVER_SCHEMA_INVALID")
        if payload.get("grant_ref") != grant_ref:
            raise RuntimeError("GRANT_RESOLVER_REF_MISMATCH")
        if payload.get("agent_id") != self.config.agent_id:
            raise RuntimeError("GRANT_RESOLVER_AGENT_MISMATCH")
        if payload.get("project_id") != project_id:
            raise RuntimeError("GRANT_RESOLVER_PROJECT_MISMATCH")
        if payload.get("target_environment") != target_environment:
            raise RuntimeError("GRANT_RESOLVER_ENVIRONMENT_MISMATCH")
        if payload.get("production") is not False or payload.get("production_locked") is not True:
            raise RuntimeError("GRANT_RESOLVER_PRODUCTION_BOUNDARY_INVALID")

        observed = payload.get("observed_at_epoch")
        if not isinstance(observed, int):
            raise RuntimeError("GRANT_RESOLVER_TIME_INVALID")
        if abs(now_epoch - observed) > self.config.max_clock_skew_seconds:
            raise RuntimeError("GRANT_RESOLVER_RESPONSE_STALE")

        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows or len(rows) > 16:
            raise RuntimeError("GRANT_RESOLVER_CHAIN_INVALID")
        by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise RuntimeError("GRANT_RESOLVER_CHAIN_INVALID")
            grant_id = str(row.get("grant_id") or "")
            if not grant_id or grant_id in by_id:
                raise RuntimeError("GRANT_RESOLVER_CHAIN_INVALID")
            by_id[grant_id] = row

        grant_id = grant_ref.removeprefix("acp-grant:")
        resolved = self.grant_resolution.resolve_grant(
            grant_id,
            by_id,
            expected_agent_id=self.config.agent_id,
            now=datetime.fromtimestamp(now_epoch, tz=timezone.utc),
        )
        runtime_grant = resolved.as_runtime_grant()
        scope = runtime_grant.get("scope") or {}
        if scope.get("project_id") != project_id:
            raise RuntimeError("GRANT_RESOLVER_PROJECT_MISMATCH")
        if scope.get("target_environment") != target_environment:
            raise RuntimeError("GRANT_RESOLVER_ENVIRONMENT_MISMATCH")
        if any(str(cap).startswith("production.") for cap in runtime_grant.get("capabilities") or []):
            raise RuntimeError("GRANT_RESOLVER_PRODUCTION_CAPABILITY_FORBIDDEN")
        return runtime_grant
