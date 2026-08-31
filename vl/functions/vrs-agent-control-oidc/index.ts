import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "vrs-agent-control-plane";
const REPOSITORY = "lundus88/fieldgis-reference";
const MAIN_REF = "refs/heads/main";
const ADMIN_WORKFLOW_REF =
  "lundus88/fieldgis-reference/.github/workflows/vl-agent-control-plane-admin.yml@refs/heads/main";
const ALLOWED_WORKFLOWS = new Set([ADMIN_WORKFLOW_REF]);

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false },
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

class AuthError extends Error {}
class RequestError extends Error {}

function b64url(input: string): Uint8Array {
  let s = input.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

async function verifyOidc(jwt: string) {
  const parts = jwt.split(".");
  if (parts.length !== 3) throw new AuthError("bad token");

  const header = JSON.parse(new TextDecoder().decode(b64url(parts[0])));
  const payload = JSON.parse(new TextDecoder().decode(b64url(parts[1])));
  const workflowRef = String(payload.job_workflow_ref || payload.workflow_ref || "");

  if (
    payload.iss !== ISSUER ||
    payload.aud !== AUDIENCE ||
    payload.repository !== REPOSITORY ||
    payload.ref !== MAIN_REF ||
    !ALLOWED_WORKFLOWS.has(workflowRef)
  ) {
    throw new AuthError("OIDC identity not allowed");
  }

  const jwksResponse = await fetch(`${ISSUER}/.well-known/jwks`);
  if (!jwksResponse.ok) throw new AuthError("OIDC JWKS unavailable");
  const jwks = await jwksResponse.json();
  const jwk = jwks.keys.find((k: Record<string, unknown>) => k.kid === header.kid);
  if (!jwk) throw new AuthError("OIDC key not found");

  const key = await crypto.subtle.importKey(
    "jwk",
    jwk,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["verify"],
  );
  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    b64url(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  if (!ok) throw new AuthError("OIDC signature invalid");

  const now = Math.floor(Date.now() / 1000);
  if (!payload.exp || payload.exp < now || !payload.iat || payload.iat > now + 60) {
    throw new AuthError("OIDC token invalid");
  }

  const runId = String(payload.run_id || "");
  const sha = String(payload.sha || "");
  const actor = String(payload.actor || "");
  if (!runId || !/^[0-9a-f]{40}$/.test(sha) || !actor) {
    throw new AuthError("OIDC evidence incomplete");
  }

  return {
    repository: REPOSITORY,
    workflow_ref: workflowRef,
    run_id: runId,
    sha,
    ref: String(payload.ref || ""),
    actor,
  };
}

function actionId(value: unknown): string {
  const id = String(value || "");
  if (!/^[A-Za-z0-9._:-]{16,160}$/.test(id)) {
    throw new RequestError("invalid action_id");
  }
  return id;
}

function uuid(value: unknown, label: string): string {
  const text = String(value || "");
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(text)) {
    throw new RequestError(`invalid ${label}`);
  }
  return text;
}

function nonEmpty(value: unknown, label: string, max = 200): string {
  const text = String(value || "").trim();
  if (!text || text.length > max) throw new RequestError(`invalid ${label}`);
  return text;
}

function capabilities(value: unknown): string[] {
  if (!Array.isArray(value) || value.length === 0 || value.length > 32) {
    throw new RequestError("invalid capabilities");
  }
  const result = value.map((v) => nonEmpty(v, "capability", 200));
  if (result.some((v) => v === "production.approve" || v === "production.promote")) {
    throw new RequestError("production capability delegation prohibited");
  }
  return [...new Set(result)].sort();
}

function scope(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new RequestError("invalid scope");
  }
  const result = value as Record<string, unknown>;
  const env = String(result.target_environment || "");
  if (env !== "development" && env !== "staging") {
    throw new RequestError("ACP live boundary is non-production only");
  }
  return result;
}

function budget(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new RequestError("invalid budget");
  }
  const b = value as Record<string, unknown>;
  for (const key of ["timeout_seconds", "max_retries", "max_cost_minor"]) {
    const v = b[key];
    if (v !== undefined && v !== null && (!Number.isInteger(v) || Number(v) < 0)) {
      throw new RequestError(`invalid budget ${key}`);
    }
  }
  return b;
}

function boundedTime(value: unknown, label: string): string {
  const text = String(value || "");
  const time = Date.parse(text);
  if (!text || Number.isNaN(time)) throw new RequestError(`invalid ${label}`);
  return new Date(time).toISOString();
}

async function delegateGrant(body: Record<string, unknown>, actorEvidence: Record<string, string>) {
  const id = actionId(body.action_id);
  const parentGrantId = uuid(body.parent_grant_id, "parent_grant_id");
  const validFrom = boundedTime(body.valid_from, "valid_from");
  const validUntil = boundedTime(body.valid_until, "valid_until");
  if (Date.parse(validUntil) <= Date.parse(validFrom)) {
    throw new RequestError("invalid validity window");
  }

  const { data, error } = await sb.rpc("acp_delegate_agent_grant_nonprod", {
    p_action_id: id,
    p_parent_grant_id: parentGrantId,
    p_agent_id: nonEmpty(body.agent_id, "agent_id", 128),
    p_agent_version: nonEmpty(body.agent_version, "agent_version", 64),
    p_role_name: nonEmpty(body.role_name, "role_name", 128),
    p_capabilities: capabilities(body.capabilities),
    p_scope: scope(body.scope),
    p_budget: budget(body.budget),
    p_valid_from: validFrom,
    p_valid_until: validUntil,
    p_actor_evidence: actorEvidence,
  });

  if (error) {
    console.error("ACP delegate RPC rejected", error.code || "unknown");
    return json({ ok: false, blocked: true, code: "ACP_POLICY_REJECTED" }, 409);
  }
  return json({ ok: true, operation: "delegate_grant", grant_id: data });
}

async function revokeGrant(body: Record<string, unknown>, actorEvidence: Record<string, string>) {
  const { data, error } = await sb.rpc("acp_revoke_agent_grant", {
    p_action_id: actionId(body.action_id),
    p_grant_id: uuid(body.grant_id, "grant_id"),
    p_reason: nonEmpty(body.reason, "reason", 500),
    p_actor_evidence: actorEvidence,
  });

  if (error) {
    console.error("ACP revoke RPC rejected", error.code || "unknown");
    return json({ ok: false, blocked: true, code: "ACP_POLICY_REJECTED" }, 409);
  }
  return json({ ok: data === true, operation: "revoke_grant" });
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST required" }, 405);

  let identity: Record<string, string>;
  try {
    const auth = req.headers.get("authorization") || "";
    if (!auth.startsWith("Bearer ")) throw new AuthError("unauthorized");
    identity = await verifyOidc(auth.slice(7));
  } catch (error) {
    const message = error instanceof AuthError ? error.message : "authentication failed";
    return json({ ok: false, blocked: true, error: message }, 401);
  }

  try {
    const parsed = await req.json();
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new RequestError("invalid request body");
    }
    const body = parsed as Record<string, unknown>;
    const operation = String(body.operation || "");

    if (operation === "delegate_grant") return await delegateGrant(body, identity);
    if (operation === "revoke_grant") return await revokeGrant(body, identity);
    throw new RequestError("unsupported operation");
  } catch (error) {
    if (error instanceof RequestError) {
      return json({ ok: false, blocked: true, error: error.message }, 400);
    }
    console.error("ACP boundary internal failure", error instanceof Error ? error.name : "unknown");
    return json({ ok: false, blocked: true, code: "ACP_INTERNAL_FAILURE" }, 500);
  }
});
