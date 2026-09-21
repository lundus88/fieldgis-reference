from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import sqlite3
import time
from typing import Any, Callable, Iterable

HUMAN_ONLY = {
    "PRODUCTION_RELEASE","PRODUCTION_DEPLOY","PRODUCTION_PROMOTION",
    "PROTECTED_MAIN_MERGE","PRODUCTION_DATA_MUTATION","AUTHORITY_WIDENING",
    "AUTH_SECURITY_POLICY_CHANGE","CREDENTIAL_WIDENING","DATA_DELETION",
    "CUSTOMER_COMMITMENT","BID_SUBMISSION","PRICING_COMMITMENT",
    "CONTRACT_COMMITMENT","FINANCIAL_COMMITMENT"
}

def digest(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

@dataclass(frozen=True)
class Observation:
    source_id: str
    observed_at: float
    ttl_seconds: int
    payload: dict[str, Any]
    evidence_id: str

    def envelope(self, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        age = max(0.0, now - self.observed_at)
        body = {
            "schema":"lom.observation/1",
            "source_id":self.source_id,
            "observed_at":self.observed_at,
            "ttl_seconds":self.ttl_seconds,
            "payload":self.payload,
            "evidence_id":self.evidence_id,
            "fresh": age <= self.ttl_seconds,
            "age_seconds": round(age, 6),
        }
        return {**body, "observation_digest":digest(body)}

class Eyes:
    def __init__(self, adapters: dict[str, Callable[[], Observation]]):
        self.adapters = adapters

    def observe(self, source_ids: Iterable[str], now: float | None = None) -> dict[str, Any]:
        items=[]
        for sid in sorted(set(source_ids)):
            adapter=self.adapters.get(sid)
            if adapter is None:
                return {"decision":"HOLD","reason":"UNKNOWN_OBSERVATION_SOURCE","source_id":sid}
            try:
                obs=adapter()
            except Exception as exc:
                return {"decision":"HOLD","reason":"OBSERVATION_FAILED","source_id":sid,"error_type":type(exc).__name__}
            if obs.source_id != sid or not obs.evidence_id or obs.ttl_seconds <= 0:
                return {"decision":"HOLD","reason":"INVALID_OBSERVATION","source_id":sid}
            env=obs.envelope(now)
            if not env["fresh"]:
                return {"decision":"HOLD","reason":"STALE_OBSERVATION","source_id":sid,"observation":env}
            items.append(env)
        body={"schema":"lom.eyes-snapshot/1","decision":"ALLOW","observations":items}
        return {**body,"snapshot_digest":digest(body)}

@dataclass(frozen=True)
class ActionRequest:
    request_id: str
    action_id: str
    capability_id: str
    idempotency_key: str
    environment: str
    risk: str
    dry_run: bool
    evidence_ids: tuple[str, ...]

@dataclass(frozen=True)
class ActionAdapter:
    capability_id: str
    certified: bool
    non_production_only: bool
    execute: Callable[[ActionRequest], dict[str, Any]]
    verify: Callable[[ActionRequest, dict[str, Any]], dict[str, Any]]

class Hands:
    def __init__(self, adapters: dict[str, ActionAdapter]):
        self.adapters=adapters
        self._seen: dict[str, dict[str, Any]]={}

    def authority(self, req: ActionRequest) -> dict[str, str]:
        if req.action_id in HUMAN_ONLY:
            return {"decision":"HUMAN_GATE","reason":"HUMAN_ONLY_ACTION"}
        if req.environment.lower() == "production":
            return {"decision":"HUMAN_GATE","reason":"PRODUCTION_HUMAN_ONLY"}
        if req.risk == "HIGH":
            return {"decision":"HUMAN_GATE","reason":"HIGH_RISK"}
        if req.risk not in {"LOW","MEDIUM"}:
            return {"decision":"HOLD","reason":"UNKNOWN_RISK"}
        if not req.request_id or not req.idempotency_key or not req.evidence_ids:
            return {"decision":"HOLD","reason":"REQUEST_EVIDENCE_INCOMPLETE"}
        return {"decision":"ALLOW","reason":"BOUNDED_NON_PRODUCTION"}

    def act(self, req: ActionRequest) -> dict[str, Any]:
        auth=self.authority(req)
        if auth["decision"] != "ALLOW":
            return {**auth,"production_locked":True}

        adapter=self.adapters.get(req.capability_id)
        if adapter is None:
            return {"decision":"HOLD","reason":"UNKNOWN_CAPABILITY","production_locked":True}
        if not adapter.certified or not adapter.non_production_only:
            return {"decision":"HOLD","reason":"CAPABILITY_NOT_ELIGIBLE","production_locked":True}

        seen=self._seen.get(req.idempotency_key)
        if seen is not None:
            return {**seen,"replayed":True}

        before={
            "request":asdict(req),
            "authority":auth,
            "adapter":{
                "capability_id":adapter.capability_id,
                "certified":adapter.certified,
                "non_production_only":adapter.non_production_only,
            }
        }
        before_digest=digest(before)

        try:
            result=adapter.execute(req)
        except Exception as exc:
            return {"decision":"HOLD","reason":"ACTION_EXECUTION_FAILED","error_type":type(exc).__name__,"before_digest":before_digest,"production_locked":True}

        verification=adapter.verify(req,result)
        if verification.get("decision") != "ALLOW":
            out={"decision":"HOLD","reason":"POST_ACTION_VERIFICATION_FAILED","before_digest":before_digest,"result":result,"verification":verification,"production_locked":True}
            self._seen[req.idempotency_key]=out
            return out

        body={
            "schema":"lom.hand-action/1",
            "decision":"ALLOW",
            "reason":"ACTION_VERIFIED",
            "request_id":req.request_id,
            "action_id":req.action_id,
            "capability_id":req.capability_id,
            "idempotency_key":req.idempotency_key,
            "dry_run":req.dry_run,
            "result":result,
            "verification":verification,
            "before_digest":before_digest,
            "production_locked":True,
        }
        out={**body,"action_digest":digest(body),"replayed":False}
        self._seen[req.idempotency_key]=out
        return out

class ContinuityStore:
    def __init__(self, path: str=":memory:"):
        self.db=sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS checkpoints (objective_id TEXT PRIMARY KEY, state_json TEXT NOT NULL, state_digest TEXT NOT NULL, updated_at REAL NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, objective_id TEXT NOT NULL, event_type TEXT NOT NULL, event_json TEXT NOT NULL, event_digest TEXT NOT NULL, created_at REAL NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS leases (objective_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, heartbeat_at REAL NOT NULL, lease_seconds INTEGER NOT NULL)")
        self.db.commit()

    def append_event(self, objective_id: str, event_type: str, event: dict[str, Any], now: float | None=None) -> str:
        now=time.time() if now is None else now
        body={"objective_id":objective_id,"event_type":event_type,"event":event,"created_at":now}
        d=digest(body)
        self.db.execute("INSERT INTO events(objective_id,event_type,event_json,event_digest,created_at) VALUES(?,?,?,?,?)",(objective_id,event_type,json.dumps(body,sort_keys=True),d,now))
        self.db.commit()
        return d

    def checkpoint(self, objective_id: str, state: dict[str, Any], now: float | None=None) -> dict[str, Any]:
        if not objective_id:
            return {"decision":"HOLD","reason":"OBJECTIVE_REQUIRED"}
        now=time.time() if now is None else now
        body={"schema":"lom.continuity-checkpoint/1","objective_id":objective_id,"state":state}
        d=digest(body)
        self.db.execute("INSERT INTO checkpoints(objective_id,state_json,state_digest,updated_at) VALUES(?,?,?,?) ON CONFLICT(objective_id) DO UPDATE SET state_json=excluded.state_json,state_digest=excluded.state_digest,updated_at=excluded.updated_at",(objective_id,json.dumps(body,sort_keys=True),d,now))
        self.db.commit()
        self.append_event(objective_id,"CHECKPOINT",{"state_digest":d},now)
        return {"decision":"ALLOW","checkpoint_digest":d,"updated_at":now}

    def resume(self, objective_id: str) -> dict[str, Any]:
        row=self.db.execute("SELECT state_json,state_digest,updated_at FROM checkpoints WHERE objective_id=?",(objective_id,)).fetchone()
        if row is None:
            return {"decision":"HOLD","reason":"CHECKPOINT_NOT_FOUND"}
        body=json.loads(row[0])
        if digest(body) != row[1]:
            return {"decision":"HOLD","reason":"CHECKPOINT_DIGEST_MISMATCH"}
        return {"decision":"ALLOW","state":body["state"],"checkpoint_digest":row[1],"updated_at":row[2]}

    def acquire_lease(self, objective_id: str, owner_id: str, lease_seconds: int, now: float | None=None) -> dict[str, Any]:
        if not objective_id or not owner_id or lease_seconds <= 0:
            return {"decision":"HOLD","reason":"INVALID_LEASE"}
        now=time.time() if now is None else now
        row=self.db.execute("SELECT owner_id,heartbeat_at,lease_seconds FROM leases WHERE objective_id=?",(objective_id,)).fetchone()
        if row is not None:
            current_owner, heartbeat_at, current_seconds=row
            if now - heartbeat_at <= current_seconds and current_owner != owner_id:
                return {"decision":"HOLD","reason":"LEASE_HELD","owner_id":current_owner}
        self.db.execute("INSERT INTO leases(objective_id,owner_id,heartbeat_at,lease_seconds) VALUES(?,?,?,?) ON CONFLICT(objective_id) DO UPDATE SET owner_id=excluded.owner_id,heartbeat_at=excluded.heartbeat_at,lease_seconds=excluded.lease_seconds",(objective_id,owner_id,now,lease_seconds))
        self.db.commit()
        self.append_event(objective_id,"LEASE_ACQUIRED",{"owner_id":owner_id,"lease_seconds":lease_seconds},now)
        return {"decision":"ALLOW","owner_id":owner_id,"lease_expires_at":now+lease_seconds}

    def heartbeat(self, objective_id: str, owner_id: str, now: float | None=None) -> dict[str, Any]:
        now=time.time() if now is None else now
        row=self.db.execute("SELECT owner_id,heartbeat_at,lease_seconds FROM leases WHERE objective_id=?",(objective_id,)).fetchone()
        if row is None or row[0] != owner_id:
            return {"decision":"HOLD","reason":"LEASE_NOT_OWNED"}
        if now - row[1] > row[2]:
            return {"decision":"HOLD","reason":"LEASE_EXPIRED"}
        self.db.execute("UPDATE leases SET heartbeat_at=? WHERE objective_id=?",(now,objective_id))
        self.db.commit()
        return {"decision":"ALLOW","heartbeat_at":now}

    def events(self, objective_id: str) -> list[dict[str, Any]]:
        rows=self.db.execute("SELECT seq,event_json,event_digest FROM events WHERE objective_id=? ORDER BY seq",(objective_id,)).fetchall()
        out=[]
        for seq,raw,d in rows:
            body=json.loads(raw)
            out.append({"seq":seq,"event":body,"event_digest":d,"digest_valid":digest(body)==d})
        return out

class Runtime:
    def __init__(self, eyes: Eyes, hands: Hands, continuity: ContinuityStore):
        self.eyes=eyes
        self.hands=hands
        self.continuity=continuity

    def cycle(self, *, objective_id: str, owner_id: str, source_ids: Iterable[str], action: ActionRequest | None, state: dict[str, Any], lease_seconds: int=60, now: float | None=None) -> dict[str, Any]:
        now=time.time() if now is None else now
        lease=self.continuity.acquire_lease(objective_id,owner_id,lease_seconds,now)
        if lease["decision"] != "ALLOW":
            return {"decision":"HOLD","stage":"LEASE","detail":lease}

        snapshot=self.eyes.observe(source_ids,now)
        if snapshot["decision"] != "ALLOW":
            self.continuity.append_event(objective_id,"EYES_HOLD",snapshot,now)
            return {"decision":"HOLD","stage":"EYES","detail":snapshot}

        action_result=None
        if action is not None:
            action_result=self.hands.act(action)
            if action_result["decision"] != "ALLOW":
                self.continuity.append_event(objective_id,"HANDS_HOLD",action_result,now)
                return {"decision":action_result["decision"],"stage":"HANDS","detail":action_result}

        checkpoint_state={
            "state":state,
            "eyes_snapshot_digest":snapshot["snapshot_digest"],
            "action_digest":None if action_result is None else action_result["action_digest"],
            "owner_id":owner_id,
        }
        cp=self.continuity.checkpoint(objective_id,checkpoint_state,now)
        body={
            "schema":"lom.runtime-cycle/1",
            "decision":"ALLOW",
            "objective_id":objective_id,
            "eyes_snapshot_digest":snapshot["snapshot_digest"],
            "action_digest":None if action_result is None else action_result["action_digest"],
            "checkpoint_digest":cp["checkpoint_digest"],
            "production_locked":True,
        }
        self.continuity.append_event(objective_id,"CYCLE_COMPLETE",body,now)
        return {**body,"cycle_digest":digest(body)}
