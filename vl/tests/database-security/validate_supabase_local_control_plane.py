#!/usr/bin/env python3
"""Validate #218 against a local Supabase stack: Postgres roles + real Data API/PostgREST.
No remote project IDs, credentials, release records, or Production mutations are used.
"""
import base64
import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

OWNER = "20000000-0000-4000-8000-000000000001"
PROJECT = "10000000-0000-4000-8000-000000000001"

API_URL = os.environ["API_URL"].rstrip("/")
ANON_KEY = os.environ["ANON_KEY"]
JWT_SECRET = os.environ["JWT_SECRET"]
DB_URL = os.environ["DB_URL"]

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def jwt(aal: str) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "aud": "authenticated",
        "exp": now + 3600,
        "iat": now,
        "sub": OWNER,
        "role": "authenticated",
        "aal": aal,
        "email": "local-owner@example.invalid",
        "app_metadata": {"provider": "email", "providers": ["email"]},
        "user_metadata": {},
    }
    signing = f"{b64url(json.dumps(header,separators=(',',':')).encode())}.{b64url(json.dumps(payload,separators=(',',':')).encode())}"
    sig = hmac.new(JWT_SECRET.encode(), signing.encode(), hashlib.sha256).digest()
    return f"{signing}.{b64url(sig)}"

def request(method: str, path: str, token: str, payload=None, extra_headers=None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(API_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()

def rpc(name: str, payload: dict, token: str):
    return request("POST", f"/rest/v1/rpc/{name}", token, payload)

def psql(sql: str) -> str:
    return subprocess.check_output(
        ["psql", DB_URL, "-v", "ON_ERROR_STOP=1", "-Atc", sql],
        text=True,
    ).strip()

def require_http(label, status, expected_2xx):
    ok = 200 <= status < 300
    if ok != expected_2xx:
        raise AssertionError(f"{label}: unexpected HTTP {status}")

anon = ANON_KEY
aal1 = jwt("aal1")
aal2 = jwt("aal2")

# Real Data API exposed-schema boundary.
status, body = request(
    "GET",
    "/rest/v1/projects?select=id&limit=1",
    anon,
    extra_headers={"Accept-Profile": "private"},
)
if status != 406 or "PGRST106" not in body:
    raise AssertionError(f"private schema exposure guard: expected 406/PGRST106, got {status} {body[:160]}")

# anon cannot invoke any governed RPC.
for name, payload in [
    ("vl_get_assisted_build_quote", {"p_complexity": "low"}),
    ("request_vrs_internal_usage_override", {
        "p_project_id": PROJECT,
        "p_reason": "Explicit local control-plane reason",
        "p_duration_minutes": 60,
    }),
    ("vl_prepare_assisted_build_product_alignment", {
        "p_answers": {
            "problem": "Track survey jobs",
            "users": "Survey coordinator",
            "current": "Spreadsheet",
            "payments": "no",
            "compliance": "Authorised staff only",
        },
        "p_structured": {
            "required_features": ["Register survey job", "View progress"],
            "proposed_workflow": "Register and track jobs.",
        },
    }),
]:
    s, _ = rpc(name, payload, anon)
    require_http(f"anon denied {name}", s, False)

# Authenticated AAL1 can use read-only quote, but cannot request privileged override.
s, body = rpc("vl_get_assisted_build_quote", {"p_complexity": "low"}, aal1)
require_http("AAL1 quote", s, True)
quote = json.loads(body)
if quote.get("commercial_amount") is not None or quote.get("production_payment_performed") is not False:
    raise AssertionError("quote contract drift")

s, body = rpc("request_vrs_internal_usage_override", {
    "p_project_id": PROJECT,
    "p_reason": "Explicit local AAL1 denial reason",
    "p_duration_minutes": 60,
}, aal1)
require_http("AAL1 override denied", s, False)
if "AAL2" not in body:
    raise AssertionError("AAL1 denial did not preserve AAL2 guard")

# Authenticated AAL2 owner succeeds through real PostgREST and cannot bypass Production governance.
s, body = rpc("request_vrs_internal_usage_override", {
    "p_project_id": PROJECT,
    "p_reason": "Explicit local AAL2 owner reason",
    "p_duration_minutes": 60,
}, aal2)
require_http("AAL2 owner override", s, True)
override = json.loads(body)
for key in ["ok", "production_approval_bypassed", "production_promotion_bypassed"]:
    if key not in override:
        raise AssertionError(f"override response missing {key}")
if override["ok"] is not True or override["production_approval_bypassed"] is not False or override["production_promotion_bypassed"] is not False:
    raise AssertionError("override governance flags drift")

s, body = rpc("vl_prepare_assisted_build_product_alignment", {
    "p_answers": {
        "problem": "Track incoming survey jobs and progress",
        "users": "Survey operations coordinator",
        "current": "Record jobs in a spreadsheet",
        "payments": "no",
        "compliance": "Access by authorised staff only",
    },
    "p_structured": {
        "required_features": ["Register survey job", "View job progress"],
        "proposed_workflow": "Register and track survey jobs.",
    },
}, aal2)
require_http("AAL2 alignment preparation", s, True)
alignment = json.loads(body)
if alignment.get("generated_for_review") is not True:
    raise AssertionError("alignment review guard drift")
if alignment.get("production_approval_performed") is not False or alignment.get("production_promotion_performed") is not False:
    raise AssertionError("alignment Production authority drift")

# Catalog and ACL evidence on the real local Postgres roles.
scanner = psql("""select
(select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace
 where n.nspname='public' and c.relkind='r' and c.relrowsecurity=false),
(select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace
 where n.nspname='public' and p.prokind='f' and p.prosecdef
 and (has_function_privilege('public',p.oid,'EXECUTE')
      or has_function_privilege('anon',p.oid,'EXECUTE')
      or has_function_privilege('authenticated',p.oid,'EXECUTE')));""")
if scanner != "0|0":
    raise AssertionError(f"scanner expected 0|0, got {scanner!r}")

private_definers = psql("""select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='private' and p.prosecdef and
(has_function_privilege('public',p.oid,'EXECUTE')
 or has_function_privilege('anon',p.oid,'EXECUTE')
 or has_function_privilege('authenticated',p.oid,'EXECUTE'));""")
if private_definers != "0":
    raise AssertionError(f"client-executable private SECURITY DEFINER count={private_definers}")

public_acl = psql("""select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public'
and p.proname in ('request_vrs_internal_usage_override','vl_get_assisted_build_quote','vl_prepare_assisted_build_product_alignment')
and p.prosecdef=false
and not has_function_privilege('public',p.oid,'EXECUTE')
and not has_function_privilege('anon',p.oid,'EXECUTE')
and has_function_privilege('authenticated',p.oid,'EXECUTE');""")
if public_acl != "3":
    raise AssertionError(f"expected 3 hardened public RPC ACLs, got {public_acl}")

raw_private_access = psql("""select count(*) from unnest(array['anon','authenticated']) role_name
cross join unnest(array['private.internal_usage_overrides','private.internal_usage_audit','private.assisted_build_cost_policy']) table_name
where has_table_privilege(role_name,table_name,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')
   or has_any_column_privilege(role_name,table_name,'SELECT,INSERT,UPDATE,REFERENCES');""")
if raw_private_access != "0":
    raise AssertionError(f"raw private table access count={raw_private_access}")

audit_count = int(psql("select count(*) from private.internal_usage_audit where actor_user_id='20000000-0000-4000-8000-000000000001'::uuid;"))
if audit_count < 1:
    raise AssertionError("successful AAL2 override did not create audit evidence")

print("VL LOCAL SUPABASE CONTROL PLANE: PASS")
print("data_api_private_schema=DENIED_PGRST106")
print("anon_rpc_access=DENIED")
print("authenticated_aal1_readonly_quote=PASS")
print("authenticated_aal1_override=DENIED_AAL2_REQUIRED")
print("authenticated_aal2_owner_override=PASS_AUDITED")
print("public_scanner=0|0")
print("client_executable_private_security_definers=0")
print("production_mutation=NONE remote_project_link=NONE")
