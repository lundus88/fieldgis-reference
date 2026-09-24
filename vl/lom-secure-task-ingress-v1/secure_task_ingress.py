from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any

SCHEMA = "lom.secure-task-ingress/1"
AUDIT_SCHEMA = "lom.secure-task-ingress-audit/1"

ALLOWED_ACTIONS = {
    "PREPARE_PREVIEW_REFRESH",
    "PREPARE_EXACT_MAIN_CI_REFRESH",
    "PREPARE_CI_REMEDIATION_PR",
    "PREPARE_RUNTIME_DIAGNOSTIC_PR",
    "PREPARE_REGRESSION_EVIDENCE_REFRESH",
    "PREPARE_JOURNEY_BINDING_PR",
    "PREPARE_NONCRITICAL_REMEDIATION_PR",
    "NON_PROD_CODE",
}
BODY_FIELDS = {
    "schema",
    "signal_id",
    "project_id",
    "route_digest",
    "requested_action",
    "steps",
    "max_authority",
    "production",
    "production_locked",
    "idempotency_key",
    "evidence_refs",
}
FORBIDDEN_KEYS = {"command", "shell", "url", "token", "secret", "credential", "script"}
TASK_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{16,200}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
GRANT_REF_RE = re.compile(r"^acp-grant:[A-Za-z0-9._:-]{1,180}$")
DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
OWNER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return "sha256:" + sha256(canonical_bytes(value)).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                return True
            if _contains_forbidden_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def sign_task(task: dict[str, Any], secret: bytes) -> str:
    if not secret:
        raise ValueError("SIGNING_SECRET_REQUIRED")
    key_id = str(task.get("signing_key_id") or "")
    if not KEY_ID_RE.fullmatch(key_id):
        raise ValueError("SIGNING_KEY_ID_REQUIRED")
    return "hmac-sha256:" + hmac.new(secret, canonical_bytes(task), sha256).hexdigest()


def verify_signature(task: dict[str, Any], signature: str, signing_keys: dict[str, bytes]) -> bool:
    key_id = str(task.get("signing_key_id") or "")
    key = signing_keys.get(key_id)
    if not key or not isinstance(signature, str) or not signature.startswith("hmac-sha256:"):
        return False
    expected = sign_task(task, key)
    return hmac.compare_digest(expected, signature)


class SecureTaskIngress:
    """Durable authenticated ingress for bounded non-Production LOM tasks.

    This store is transport/continuity state only. It is never an authority store.
    Caller-supplied grants are not accepted. Downstream must resolve grant_ref from
    the authoritative ACP store before policy evaluation and execution.
    """

    def __init__(
        self,
        *,
        store_path: str | Path,
        signing_keys: dict[str, bytes],
        max_queue: int = 64,
        max_ttl_seconds: int = 900,
        max_envelope_bytes: int = 65536,
        max_submissions_per_minute: int = 30,
        max_attempts: int = 3,
    ) -> None:
        if not signing_keys or any(not KEY_ID_RE.fullmatch(k) or not v for k, v in signing_keys.items()):
            raise ValueError("SIGNING_KEYRING_REQUIRED")
        if max_queue < 1 or max_queue > 1024:
            raise ValueError("QUEUE_BOUND_INVALID")
        if max_ttl_seconds < 30 or max_ttl_seconds > 3600:
            raise ValueError("TTL_BOUND_INVALID")
        if max_envelope_bytes < 1024 or max_envelope_bytes > 262144:
            raise ValueError("ENVELOPE_SIZE_BOUND_INVALID")
        if max_submissions_per_minute < 1 or max_submissions_per_minute > 600:
            raise ValueError("RATE_BOUND_INVALID")
        if max_attempts < 1 or max_attempts > 10:
            raise ValueError("ATTEMPT_BOUND_INVALID")

        self.store_path = str(store_path)
        self.signing_keys = dict(signing_keys)
        self.max_queue = max_queue
        self.max_ttl_seconds = max_ttl_seconds
        self.max_envelope_bytes = max_envelope_bytes
        self.max_submissions_per_minute = max_submissions_per_minute
        self.max_attempts = max_attempts
        self.db = sqlite3.connect(self.store_path, timeout=5.0)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def close(self) -> None:
        self.db.close()

    def _init_schema(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
              task_id TEXT PRIMARY KEY,
              envelope_digest TEXT NOT NULL,
              envelope_json TEXT NOT NULL,
              tenant TEXT NOT NULL,
              priority INTEGER NOT NULL,
              accepted_at REAL NOT NULL,
              expires_at REAL NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('PENDING','LEASED','ACKED','HOLD')),
              lease_owner TEXT,
              lease_token TEXT,
              lease_expires_at REAL,
              attempt_count INTEGER NOT NULL DEFAULT 0,
              result_digest TEXT,
              last_reason TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_ingress_tasks_state
              ON tasks(state, priority DESC, accepted_at ASC);
            CREATE INDEX IF NOT EXISTS idx_ingress_tasks_tenant_time
              ON tasks(tenant, accepted_at);

            CREATE TABLE IF NOT EXISTS tenant_state (
              tenant TEXT PRIMARY KEY,
              last_claim_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
              seq INTEGER PRIMARY KEY,
              task_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              event_json TEXT NOT NULL,
              previous_digest TEXT NOT NULL,
              event_digest TEXT NOT NULL,
              created_at REAL NOT NULL
            );
            """
        )
        self.db.commit()

    def _hold(self, reason: str, **extra: Any) -> dict[str, Any]:
        return {
            "decision": "HOLD",
            "reason": reason,
            "production": False,
            "production_locked": True,
            **extra,
        }

    def _append_event(
        self,
        cur: sqlite3.Cursor,
        *,
        task_id: str,
        event_type: str,
        event: dict[str, Any],
        now_epoch: float,
    ) -> str:
        tail = cur.execute(
            "SELECT seq,event_digest FROM audit_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        sequence = 1 if tail is None else int(tail["seq"]) + 1
        previous = "GENESIS" if tail is None else str(tail["event_digest"])
        body = {
            "schema": AUDIT_SCHEMA,
            "sequence": sequence,
            "previous_digest": previous,
            "task_id": task_id,
            "event_type": event_type,
            "event": event,
            "created_at_epoch": now_epoch,
        }
        event_digest = digest(body)
        cur.execute(
            """
            INSERT INTO audit_events(
              seq,task_id,event_type,event_json,previous_digest,event_digest,created_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                sequence,
                task_id,
                event_type,
                canonical_bytes(body).decode("utf-8"),
                previous,
                event_digest,
                now_epoch,
            ),
        )
        return event_digest

    def verify_audit_chain(self) -> dict[str, Any]:
        rows = self.db.execute("SELECT * FROM audit_events ORDER BY seq").fetchall()
        previous = "GENESIS"
        for expected, row in enumerate(rows, start=1):
            if int(row["seq"]) != expected or str(row["previous_digest"]) != previous:
                return {"status": "HOLD", "reason": "AUDIT_CHAIN_MISMATCH"}
            try:
                body = json.loads(row["event_json"])
            except json.JSONDecodeError:
                return {"status": "HOLD", "reason": "AUDIT_JSON_INVALID"}
            if (
                body.get("schema") != AUDIT_SCHEMA
                or body.get("sequence") != expected
                or body.get("previous_digest") != previous
            ):
                return {"status": "HOLD", "reason": "AUDIT_BODY_MISMATCH"}
            if digest(body) != row["event_digest"]:
                return {"status": "HOLD", "reason": "AUDIT_DIGEST_MISMATCH"}
            previous = str(row["event_digest"])
        return {"status": "READY", "count": len(rows), "tail": previous}

    def _validate_envelope(self, envelope: dict[str, Any], now: datetime) -> dict[str, Any]:
        required = {
            "schema",
            "task_id",
            "issued_at",
            "expires_at",
            "tenant",
            "priority",
            "idempotency_key",
            "body_request",
            "grant_ref",
            "target_environment",
            "evidence_refs",
            "signing_key_id",
        }
        if set(envelope) != required:
            return self._hold("ENVELOPE_FIELDS_INVALID")
        if envelope.get("schema") != SCHEMA:
            return self._hold("INGRESS_SCHEMA_INVALID")

        task_id = str(envelope.get("task_id") or "")
        tenant = str(envelope.get("tenant") or "")
        grant_ref = str(envelope.get("grant_ref") or "")
        key_id = str(envelope.get("signing_key_id") or "")
        if not TASK_ID_RE.fullmatch(task_id):
            return self._hold("TASK_ID_INVALID")
        if not SAFE_ID_RE.fullmatch(tenant) or len(tenant) > 128:
            return self._hold("TENANT_INVALID")
        if not GRANT_REF_RE.fullmatch(grant_ref):
            return self._hold("AUTHORITATIVE_GRANT_REF_REQUIRED")
        if not KEY_ID_RE.fullmatch(key_id) or key_id not in self.signing_keys:
            return self._hold("SIGNING_KEY_ID_UNKNOWN")

        issued = _parse_time(envelope.get("issued_at"))
        expires = _parse_time(envelope.get("expires_at"))
        if issued is None or expires is None or expires <= issued:
            return self._hold("TASK_TIME_INVALID")
        if issued > now or expires <= now:
            return self._hold("TASK_EXPIRED_OR_FUTURE")
        ttl = int((expires - issued).total_seconds())
        if ttl > self.max_ttl_seconds:
            return self._hold("TASK_TTL_EXCEEDS_BOUND")

        priority = envelope.get("priority")
        if not isinstance(priority, int) or priority < 0 or priority > 100:
            return self._hold("PRIORITY_INVALID")

        target_environment = envelope.get("target_environment")
        if target_environment not in {"development", "staging"}:
            return self._hold("NON_PRODUCTION_SCOPE_REQUIRED")

        idem = str(envelope.get("idempotency_key") or "")
        if not DIGEST_RE.fullmatch(idem):
            return self._hold("IDEMPOTENCY_KEY_INVALID")

        body = envelope.get("body_request")
        evidence_refs = envelope.get("evidence_refs")
        if not isinstance(body, dict):
            return self._hold("BOUNDED_REQUEST_REQUIRED")
        if set(body) != BODY_FIELDS:
            return self._hold("BODY_FIELDS_INVALID")
        if _contains_forbidden_key(body):
            return self._hold("ARBITRARY_EXECUTION_PRIMITIVE_FORBIDDEN")
        if body.get("schema") != "lom.organism-bounded-delegation/1":
            return self._hold("BODY_SCHEMA_INVALID")
        if body.get("production") is not False or body.get("production_locked") is not True:
            return self._hold("PRODUCTION_BOUNDARY_INVALID")
        if body.get("max_authority") != "PREPARE_PR":
            return self._hold("AUTHORITY_CEILING_INVALID")
        if body.get("requested_action") not in ALLOWED_ACTIONS:
            return self._hold("BODY_ACTION_NOT_REGISTERED")
        if body.get("idempotency_key") != idem:
            return self._hold("IDEMPOTENCY_BINDING_MISMATCH")

        if not SAFE_ID_RE.fullmatch(str(body.get("signal_id") or "")):
            return self._hold("SIGNAL_ID_INVALID")
        if not SAFE_ID_RE.fullmatch(str(body.get("project_id") or "")):
            return self._hold("PROJECT_ID_INVALID")
        if not DIGEST_RE.fullmatch(str(body.get("route_digest") or "")):
            return self._hold("ROUTE_DIGEST_INVALID")

        steps = body.get("steps")
        if (
            not isinstance(steps, list)
            or not steps
            or len(steps) > 32
            or any(not isinstance(step, str) or not re.fullmatch(r"[A-Z0-9._:-]{1,128}", step) for step in steps)
        ):
            return self._hold("BODY_STEPS_INVALID")

        if (
            not isinstance(evidence_refs, list)
            or not evidence_refs
            or len(evidence_refs) > 32
            or any(not isinstance(ref, str) or not ref or len(ref) > 256 for ref in evidence_refs)
        ):
            return self._hold("INGRESS_EVIDENCE_INVALID")
        if body.get("evidence_refs") != evidence_refs:
            return self._hold("EVIDENCE_BINDING_MISMATCH")

        return {
            "decision": "VALID",
            "task_id": task_id,
            "tenant": tenant,
            "priority": priority,
            "expires_at_epoch": expires.timestamp(),
        }

    def submit(
        self,
        envelope: dict[str, Any],
        signature: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if not isinstance(envelope, dict):
            return self._hold("ENVELOPE_OBJECT_REQUIRED")
        try:
            raw = canonical_bytes(envelope)
        except (TypeError, ValueError):
            return self._hold("ENVELOPE_JSON_INVALID")
        if len(raw) > self.max_envelope_bytes:
            return self._hold("ENVELOPE_TOO_LARGE")
        if not verify_signature(envelope, signature, self.signing_keys):
            return self._hold("SIGNATURE_INVALID")

        validated = self._validate_envelope(envelope, now)
        if validated.get("decision") != "VALID":
            return validated

        task_id = validated["task_id"]
        tenant = validated["tenant"]
        now_epoch = now.timestamp()
        envelope_digest = digest(envelope)

        cur = self.db.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            existing = cur.execute(
                "SELECT envelope_digest,state FROM tasks WHERE task_id=?",
                (task_id,),
            ).fetchone()
            if existing is not None:
                self.db.rollback()
                if existing["envelope_digest"] == envelope_digest:
                    return {
                        "decision": "ACCEPTED_IDEMPOTENT",
                        "reason": "IDENTICAL_TASK_ALREADY_RECORDED",
                        "task_id": task_id,
                        "state": existing["state"],
                        "production": False,
                        "production_locked": True,
                    }
                return self._hold("TASK_ID_REPLAY_MISMATCH")

            recent = cur.execute(
                "SELECT COUNT(*) AS n FROM tasks WHERE tenant=? AND accepted_at>=?",
                (tenant, now_epoch - 60.0),
            ).fetchone()["n"]
            if int(recent) >= self.max_submissions_per_minute:
                self.db.rollback()
                return self._hold("TENANT_RATE_LIMIT_REACHED")

            active = cur.execute(
                "SELECT COUNT(*) AS n FROM tasks WHERE state IN ('PENDING','LEASED')"
            ).fetchone()["n"]
            if int(active) >= self.max_queue:
                self.db.rollback()
                return self._hold("QUEUE_CAPACITY_REACHED")

            cur.execute(
                """
                INSERT INTO tasks(
                  task_id,envelope_digest,envelope_json,tenant,priority,
                  accepted_at,expires_at,state
                ) VALUES(?,?,?,?,?,?,?,'PENDING')
                """,
                (
                    task_id,
                    envelope_digest,
                    raw.decode("utf-8"),
                    tenant,
                    validated["priority"],
                    now_epoch,
                    validated["expires_at_epoch"],
                ),
            )
            audit_digest = self._append_event(
                cur,
                task_id=task_id,
                event_type="TASK_ACCEPTED",
                event={"envelope_digest": envelope_digest, "tenant": tenant},
                now_epoch=now_epoch,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "decision": "ACCEPTED",
            "reason": "AUTHENTICATED_BOUNDED_TASK_PERSISTED",
            "task_id": task_id,
            "queue_depth": self._active_count(),
            "envelope_digest": envelope_digest,
            "audit_event_digest": audit_digest,
            "production": False,
            "production_locked": True,
            "execution_performed": False,
        }

    def _active_count(self) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE state IN ('PENDING','LEASED')"
        ).fetchone()
        return int(row["n"])

    def _sweep_expired(self, cur: sqlite3.Cursor, now_epoch: float) -> None:
        pending = cur.execute(
            "SELECT task_id FROM tasks WHERE state='PENDING' AND expires_at<=?",
            (now_epoch,),
        ).fetchall()
        for row in pending:
            cur.execute(
                "UPDATE tasks SET state='HOLD',last_reason='TASK_EXPIRED_BEFORE_CLAIM' WHERE task_id=?",
                (row["task_id"],),
            )
            self._append_event(
                cur,
                task_id=row["task_id"],
                event_type="TASK_HELD",
                event={"reason": "TASK_EXPIRED_BEFORE_CLAIM"},
                now_epoch=now_epoch,
            )

        leased = cur.execute(
            """
            SELECT task_id,expires_at,attempt_count
            FROM tasks
            WHERE state='LEASED' AND lease_expires_at<=?
            """,
            (now_epoch,),
        ).fetchall()
        for row in leased:
            if float(row["expires_at"]) <= now_epoch:
                state, reason = "HOLD", "TASK_EXPIRED_AFTER_LEASE"
            elif int(row["attempt_count"]) >= self.max_attempts:
                state, reason = "HOLD", "MAX_ATTEMPTS_REACHED"
            else:
                state, reason = "PENDING", "LEASE_EXPIRED_REQUEUED"
            cur.execute(
                """
                UPDATE tasks
                SET state=?,lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL,last_reason=?
                WHERE task_id=?
                """,
                (state, reason, row["task_id"]),
            )
            self._append_event(
                cur,
                task_id=row["task_id"],
                event_type="LEASE_RECOVERY",
                event={"state": state, "reason": reason},
                now_epoch=now_epoch,
            )

    def claim_next(
        self,
        *,
        owner_id: str,
        lease_seconds: int = 60,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        now_epoch = now.timestamp()
        if not OWNER_RE.fullmatch(owner_id):
            return self._hold("LEASE_OWNER_INVALID")
        if lease_seconds < 1 or lease_seconds > 300:
            return self._hold("LEASE_DURATION_INVALID")

        cur = self.db.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            self._sweep_expired(cur, now_epoch)
            row = cur.execute(
                """
                SELECT t.*
                FROM tasks t
                LEFT JOIN tenant_state s ON s.tenant=t.tenant
                WHERE t.state='PENDING' AND t.expires_at>?
                ORDER BY
                  t.priority DESC,
                  COALESCE(s.last_claim_at, 0) ASC,
                  t.accepted_at ASC,
                  t.task_id ASC
                LIMIT 1
                """,
                (now_epoch,),
            ).fetchone()
            if row is None:
                self.db.commit()
                return self._hold("QUEUE_EMPTY")

            lease_token = secrets.token_hex(24)
            lease_expires_at = min(now_epoch + lease_seconds, float(row["expires_at"]))
            attempt = int(row["attempt_count"]) + 1
            cur.execute(
                """
                UPDATE tasks
                SET state='LEASED',lease_owner=?,lease_token=?,lease_expires_at=?,
                    attempt_count=?,last_reason='LEASE_ACQUIRED'
                WHERE task_id=? AND state='PENDING'
                """,
                (owner_id, lease_token, lease_expires_at, attempt, row["task_id"]),
            )
            if cur.rowcount != 1:
                self.db.rollback()
                return self._hold("LEASE_RACE_LOST")
            cur.execute(
                """
                INSERT INTO tenant_state(tenant,last_claim_at)
                VALUES(?,?)
                ON CONFLICT(tenant) DO UPDATE SET last_claim_at=excluded.last_claim_at
                """,
                (row["tenant"], now_epoch),
            )
            audit_digest = self._append_event(
                cur,
                task_id=row["task_id"],
                event_type="LEASE_ACQUIRED",
                event={
                    "owner_id": owner_id,
                    "attempt": attempt,
                    "lease_expires_at_epoch": lease_expires_at,
                },
                now_epoch=now_epoch,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "decision": "CLAIMED",
            "reason": "DURABLE_LEASE_ACQUIRED",
            "task_id": row["task_id"],
            "lease_token": lease_token,
            "lease_expires_at_epoch": lease_expires_at,
            "attempt": attempt,
            "envelope_digest": row["envelope_digest"],
            "envelope": json.loads(row["envelope_json"]),
            "audit_event_digest": audit_digest,
            "queue_depth": self._active_count(),
            "production": False,
            "production_locked": True,
        }

    def ack(
        self,
        *,
        task_id: str,
        lease_token: str,
        result_digest: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        now_epoch = now.timestamp()
        if not TASK_ID_RE.fullmatch(task_id) or not lease_token:
            return self._hold("ACK_IDENTITY_INVALID")
        if not DIGEST_RE.fullmatch(result_digest):
            return self._hold("RESULT_DIGEST_INVALID")

        cur = self.db.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            row = cur.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                self.db.rollback()
                return self._hold("TASK_NOT_FOUND")
            if row["state"] != "LEASED" or row["lease_token"] != lease_token:
                self.db.rollback()
                return self._hold("LEASE_TOKEN_MISMATCH")
            if float(row["lease_expires_at"]) <= now_epoch:
                self.db.rollback()
                return self._hold("LEASE_EXPIRED")

            cur.execute(
                """
                UPDATE tasks
                SET state='ACKED',result_digest=?,last_reason='ACKED',
                    lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL
                WHERE task_id=?
                """,
                (result_digest, task_id),
            )
            audit_digest = self._append_event(
                cur,
                task_id=task_id,
                event_type="TASK_ACKED",
                event={"result_digest": result_digest},
                now_epoch=now_epoch,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "decision": "ACKED",
            "reason": "TASK_RESULT_COMMITTED",
            "task_id": task_id,
            "result_digest": result_digest,
            "audit_event_digest": audit_digest,
            "production": False,
            "production_locked": True,
        }

    def nack(
        self,
        *,
        task_id: str,
        lease_token: str,
        reason: str,
        permanent: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        now_epoch = now.timestamp()
        if not TASK_ID_RE.fullmatch(task_id) or not lease_token:
            return self._hold("NACK_IDENTITY_INVALID")
        if not re.fullmatch(r"[A-Z0-9._:-]{1,160}", reason):
            return self._hold("NACK_REASON_INVALID")

        cur = self.db.cursor()
        try:
            cur.execute("BEGIN IMMEDIATE")
            row = cur.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                self.db.rollback()
                return self._hold("TASK_NOT_FOUND")
            if row["state"] != "LEASED" or row["lease_token"] != lease_token:
                self.db.rollback()
                return self._hold("LEASE_TOKEN_MISMATCH")
            if float(row["lease_expires_at"]) <= now_epoch:
                self.db.rollback()
                return self._hold("LEASE_EXPIRED")

            terminal = (
                permanent
                or int(row["attempt_count"]) >= self.max_attempts
                or float(row["expires_at"]) <= now_epoch
            )
            state = "HOLD" if terminal else "PENDING"
            cur.execute(
                """
                UPDATE tasks
                SET state=?,last_reason=?,lease_owner=NULL,lease_token=NULL,lease_expires_at=NULL
                WHERE task_id=?
                """,
                (state, reason, task_id),
            )
            audit_digest = self._append_event(
                cur,
                task_id=task_id,
                event_type="TASK_NACKED",
                event={"reason": reason, "state": state},
                now_epoch=now_epoch,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "decision": "HELD" if state == "HOLD" else "REQUEUED",
            "reason": reason,
            "task_id": task_id,
            "state": state,
            "audit_event_digest": audit_digest,
            "production": False,
            "production_locked": True,
        }

    def task_status(self, task_id: str) -> dict[str, Any]:
        row = self.db.execute(
            """
            SELECT task_id,state,attempt_count,result_digest,last_reason,
                   lease_owner,lease_expires_at
            FROM tasks WHERE task_id=?
            """,
            (task_id,),
        ).fetchone()
        if row is None:
            return self._hold("TASK_NOT_FOUND")
        return {
            "decision": "STATUS",
            "task_id": row["task_id"],
            "state": row["state"],
            "attempt_count": int(row["attempt_count"]),
            "result_digest": row["result_digest"],
            "last_reason": row["last_reason"],
            "lease_owner": row["lease_owner"],
            "lease_expires_at_epoch": row["lease_expires_at"],
            "production": False,
            "production_locked": True,
        }

    def status(self) -> dict[str, Any]:
        rows = self.db.execute(
            "SELECT state,COUNT(*) AS n FROM tasks GROUP BY state"
        ).fetchall()
        counts = {row["state"]: int(row["n"]) for row in rows}
        audit = self.verify_audit_chain()
        return {
            "schema": "lom.secure-task-ingress-status/1",
            "states": counts,
            "queue_depth": counts.get("PENDING", 0) + counts.get("LEASED", 0),
            "queue_capacity": self.max_queue,
            "audit_chain": audit,
            "production": False,
            "production_locked": True,
            "self_grant": "FORBIDDEN",
            "caller_supplied_grant": "FORBIDDEN",
            "authoritative_grant_resolution": "REQUIRED_DOWNSTREAM",
            "arbitrary_shell": "FORBIDDEN",
            "connector_execution": "FORBIDDEN",
            "autonomous_ceiling": "PREPARE_PR",
            "persistence": "SQLITE_WAL_DURABLE_TRANSPORT_STATE",
            "delivery": "LEASE_ACK_NACK",
        }
