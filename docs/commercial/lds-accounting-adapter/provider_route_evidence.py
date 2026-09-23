#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict, Iterable
from datetime import datetime, timezone
import re

SHA256_RE=re.compile(r"^[0-9a-f]{64}$")
ALLOWED_METHODS={"GET","POST","PUT","PATCH","DELETE"}

@dataclass(frozen=True)
class RouteEvidence:
    operation: str
    method: str
    path: str
    request_schema_digest: str
    response_schema_digest: str
    source_reference: str
    verified_by: str
    verified_at: str
    staging_only: bool = True

    def validate(self) -> Dict:
        if not self.operation:
            return {"status":"HOLD","reason":"OPERATION_REQUIRED"}
        if self.method.upper() not in ALLOWED_METHODS:
            return {"status":"HOLD","reason":"METHOD_INVALID","operation":self.operation}
        if not self.path.startswith("/") or self.path.startswith("//"):
            return {"status":"HOLD","reason":"PATH_INVALID","operation":self.operation}
        if not SHA256_RE.match(self.request_schema_digest):
            return {"status":"HOLD","reason":"REQUEST_SCHEMA_DIGEST_INVALID","operation":self.operation}
        if not SHA256_RE.match(self.response_schema_digest):
            return {"status":"HOLD","reason":"RESPONSE_SCHEMA_DIGEST_INVALID","operation":self.operation}
        if not self.source_reference:
            return {"status":"HOLD","reason":"SOURCE_REFERENCE_REQUIRED","operation":self.operation}
        if not self.verified_by:
            return {"status":"HOLD","reason":"VERIFIER_REQUIRED","operation":self.operation}
        try:
            ts=datetime.fromisoformat(self.verified_at.replace("Z","+00:00"))
        except ValueError:
            return {"status":"HOLD","reason":"VERIFIED_AT_INVALID","operation":self.operation}
        if ts.tzinfo is None:
            return {"status":"HOLD","reason":"VERIFIED_AT_TIMEZONE_REQUIRED","operation":self.operation}
        if not self.staging_only:
            return {"status":"HOLD","reason":"PRODUCTION_ROUTE_EVIDENCE_FORBIDDEN_IN_P1","operation":self.operation}
        return {"status":"PASS","operation":self.operation}

def verify_registry(required_operations:Iterable[str], evidences:Iterable[RouteEvidence])->Dict:
    required=set(required_operations)
    by_op={}
    for evidence in evidences:
        result=evidence.validate()
        if result["status"]!="PASS":
            return result
        if evidence.operation in by_op:
            return {"status":"HOLD","reason":"DUPLICATE_ROUTE_EVIDENCE","operation":evidence.operation}
        by_op[evidence.operation]=evidence

    missing=sorted(required-set(by_op))
    extra=sorted(set(by_op)-required)
    if missing:
        return {"status":"HOLD","reason":"ROUTE_EVIDENCE_INCOMPLETE","missing":missing,"extra":extra}
    return {
        "status":"PASS",
        "reason":"ROUTE_EVIDENCE_COMPLETE",
        "operations":sorted(required),
        "extra":extra,
        "production_authority":False,
    }
