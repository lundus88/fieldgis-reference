import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const X_KEY = (Deno.env.get("BILLPLZ_X_SIGNATURE_KEY") || "").trim();
const db = createClient(SUPABASE_URL, SERVICE_KEY, { auth: { persistSession: false } });
const enc = new TextEncoder();
const J = (b: unknown, s = 200) => new Response(JSON.stringify(b), {
  status: s,
  headers: { "content-type": "application/json", "cache-control": "no-store" },
});

function canonical(p: Record<string,string>) {
  return Object.entries(p)
    .filter(([k]) => k !== "x_signature")
    .map(([k,v]) => `${k}${v ?? ""}`)
    .sort((a,b) => a.toLowerCase().localeCompare(b.toLowerCase()))
    .join("|");
}
async function hmacHex(message: string, secret: string) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return [...new Uint8Array(sig)].map(b => b.toString(16).padStart(2,"0")).join("");
}
function equalConst(a: string, b: string) {
  if (a.length !== b.length) return false;
  let n = 0;
  for (let i=0;i<a.length;i++) n |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return n === 0;
}
function normalize(p: Record<string,string>) {
  const paid = String(p.paid || "").toLowerCase() === "true";
  const state = String(p.state || "").toLowerCase();
  if (paid && state === "paid") return "paid";
  if (state === "deleted") return "cancelled";
  return "pending";
}
async function sha256(text: string) {
  const d = await crypto.subtle.digest("SHA-256", enc.encode(text));
  return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2,"0")).join("");
}

Deno.serve(async req => {
  if (req.method !== "POST") return J({ error: "POST required" }, 405);
  if (!X_KEY) return J({ error: "webhook signature key not configured", blocked: true }, 503);

  const ct = req.headers.get("content-type") || "";
  const p: Record<string,string> = {};
  if (ct.includes("application/json")) {
    const body = await req.json().catch(() => ({}));
    for (const [k,v] of Object.entries(body || {})) p[k] = v == null ? "" : String(v);
  } else {
    for (const [k,v] of new URLSearchParams(await req.text()).entries()) p[k] = v;
  }

  const received = p.x_signature || "";
  const valid = !!received && equalConst(received, await hmacHex(canonical(p), X_KEY));
  const status = normalize(p);
  const billId = p.id || "";
  const transactionId = p.transaction_id || "no-tx";
  const eventKey = `billplz-prod:${billId}:${transactionId}:${status}`;
  const payloadHash = await sha256(JSON.stringify(Object.fromEntries(Object.entries(p).filter(([k]) => k !== "x_signature"))));
  const amount = Number(p.amount || 0);

  if (!valid) return J({ error: "invalid signature" }, 401);
  if (!billId || !Number.isInteger(amount) || amount <= 0) return J({ error: "invalid payment payload", blocked: true }, 409);

  const { data, error } = await db.rpc("vl_apply_billplz_production_webhook", {
    p_event_key: eventKey,
    p_provider_bill_id: billId,
    p_payload_sha256: payloadHash,
    p_normalized_status: status,
    p_amount_minor: amount,
  });
  if (error) {
    const msg = String(error.message || error);
    if (msg.includes("unknown production bill")) return J({ error: "unknown production bill", blocked: true }, 404);
    if (msg.includes("amount mismatch") || msg.includes("invariant")) return J({ error: msg, blocked: true }, 409);
    return J({ error: "webhook processing failed" }, 500);
  }
  return J(data);
});
