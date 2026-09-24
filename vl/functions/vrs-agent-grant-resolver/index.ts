import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const QUERY_SECRET = Deno.env.get("LOM_VPS_GRANT_QUERY_SECRET")!;
const KEY_ID = Deno.env.get("LOM_VPS_GRANT_QUERY_KEY_ID") || "vps-query-v1";
const MAX_CLOCK_SKEW = 90;

const sb = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false },
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

class AuthError extends Error {}
class RequestError extends Error {}

function stable(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(stable).join(",") + "]";
  const obj = value as Record<string, unknown>;
  return "{" + Object.keys(obj).sort().map((k) => JSON.stringify(k) + ":" + stable(obj[k])).join(",") + "}";
}

function hex(bytes: ArrayBuffer): string {
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function verifyHmac(req: Request, raw: string) {
  const keyId = req.headers.get("x-lom-key-id") || "";
  const supplied = req.headers.get("x-lom-signature") || "";
  if (keyId !== KEY_ID || !QUERY_SECRET || !supplied.startsWith("hmac-sha256:")) {
    throw new AuthError("unauthorized");
  }
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(QUERY_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signed = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw));
  const expected = "hmac-sha256:" + hex(signed);
  const a = new TextEncoder().encode(expected);
  const b = new TextEncoder().encode(supplied);
  if (a.length !== b.length) throw new AuthError("unauthorized");
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  if (diff !== 0) throw new AuthError("unauthorized");
}

function text(value: unknown, label: string, max = 200): string {
  const out = String(value || "").trim();
  if (!out || out.length > max) throw new RequestError("invalid " + label);
  return out;
}

function grantRef(value: unknown): string {
  const out = text(value, "grant_ref", 220);
  if (!/^acp-grant:[0-9a-f-]{36}$/i.test(out)) throw new RequestError("invalid grant_ref");
  return out;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ ok: false, blocked: true, error: "POST required" }, 405);

  try {
    const raw = await req.text();
    if (raw.length > 16384) throw new RequestError("request too large");
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new RequestError("invalid body");

    const body = parsed as Record<string, unknown>;
    const canonical = stable(body);
    if (canonical !== raw) throw new RequestError("body must be canonical JSON");
    await verifyHmac(req, canonical);

    if (body.schema !== "lom.acp-grant-query/1") throw new RequestError("invalid schema");
    const issued = Number(body.issued_at_epoch);
    const now = Math.floor(Date.now() / 1000);
    if (!Number.isInteger(issued) || Math.abs(now - issued) > MAX_CLOCK_SKEW) {
      throw new AuthError("stale request");
    }
    const nonce = text(body.nonce, "nonce", 64);
    if (!/^[0-9a-f]{32}$/i.test(nonce)) throw new RequestError("invalid nonce");

    const ref = grantRef(body.grant_ref);
    const grantId = ref.slice("acp-grant:".length);
    const agentId = text(body.agent_id, "agent_id", 128);
    const projectId = text(body.project_id, "project_id", 200);
    const targetEnvironment = text(body.target_environment, "target_environment", 32);
    if (targetEnvironment !== "development" && targetEnvironment !== "staging") {
      throw new RequestError("non-production scope required");
    }

    const { data, error } = await sb.rpc("acp_read_agent_grant_chain_nonprod", {
      p_grant_id: grantId,
      p_agent_id: agentId,
      p_project_id: projectId,
      p_target_environment: targetEnvironment,
    });
    if (error) {
      console.error("ACP read resolver rejected", error.code || "unknown");
      return json({ ok: false, blocked: true, code: "ACP_GRANT_QUERY_REJECTED" }, 409);
    }
    if (!Array.isArray(data) || data.length < 1 || data.length > 16) {
      return json({ ok: false, blocked: true, code: "ACP_GRANT_CHAIN_INVALID" }, 409);
    }

    return json({
      schema: "lom.acp-grant-chain-response/1",
      grant_ref: ref,
      agent_id: agentId,
      project_id: projectId,
      target_environment: targetEnvironment,
      observed_at_epoch: now,
      rows: data,
      production: false,
      production_locked: true,
    });
  } catch (error) {
    if (error instanceof AuthError) {
      return json({ ok: false, blocked: true, error: error.message }, 401);
    }
    if (error instanceof RequestError || error instanceof SyntaxError) {
      return json({ ok: false, blocked: true, error: error.message }, 400);
    }
    console.error("ACP resolver internal failure", error instanceof Error ? error.name : "unknown");
    return json({ ok: false, blocked: true, code: "ACP_RESOLVER_INTERNAL_FAILURE" }, 500);
  }
});
