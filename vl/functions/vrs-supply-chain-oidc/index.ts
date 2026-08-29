import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "vrs-supply-chain-attestation";
const REPOSITORY = "lundus88/fieldgis-reference";
const MAIN_REF = "refs/heads/main";
const ALLOWED_WORKFLOWS = new Set([
  "lundus88/fieldgis-reference/.github/workflows/vl-supply-chain-attestation.yml@refs/heads/main",
]);
const sb = createClient(SUPABASE_URL, SERVICE_ROLE, { auth: { persistSession: false } });

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json" },
});

function b64url(input: string): Uint8Array {
  let s = input.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

async function verifyOidc(jwt: string) {
  const parts = jwt.split(".");
  if (parts.length !== 3) throw new Error("bad token");
  const header = JSON.parse(new TextDecoder().decode(b64url(parts[0])));
  const payload = JSON.parse(new TextDecoder().decode(b64url(parts[1])));
  const workflowRef = String(payload.job_workflow_ref || payload.workflow_ref || "");
  if (payload.iss !== ISSUER || payload.aud !== AUDIENCE || payload.repository !== REPOSITORY || payload.ref !== MAIN_REF || !ALLOWED_WORKFLOWS.has(workflowRef)) {
    throw new Error("OIDC identity not allowed");
  }
  const jwks = await (await fetch(`${ISSUER}/.well-known/jwks`)).json();
  const jwk = jwks.keys.find((k: any) => k.kid === header.kid);
  if (!jwk) throw new Error("OIDC key not found");
  const key = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
  const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", key, b64url(parts[2]), new TextEncoder().encode(`${parts[0]}.${parts[1]}`));
  if (!ok) throw new Error("OIDC signature invalid");
  const now = Math.floor(Date.now() / 1000);
  if (!payload.exp || payload.exp < now || payload.iat > now + 60) throw new Error("OIDC token invalid");
  return {
    workflow_ref: workflowRef,
    run_id: String(payload.run_id || ""),
    sha: String(payload.sha || ""),
    ref: String(payload.ref || ""),
  };
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST required" }, 405);
  try {
    const auth = req.headers.get("authorization") || "";
    if (!auth.startsWith("Bearer ")) return json({ error: "unauthorized" }, 401);
    const identity = await verifyOidc(auth.slice(7));
    const body = await req.json().catch(() => ({}));
    const factoryRunId = String(body.factory_run_id || "");
    const artifactSha256 = String(body.artifact_sha256 || "").toLowerCase();
    const buildWorkflowRunId = String(body.build_workflow_run_id || "");
    const sbomSha256 = String(body.sbom_sha256 || "").toLowerCase();
    const provenanceVerified = body.provenance_verified === true;
    const sbomVerified = body.sbom_verified === true;
    if (!factoryRunId || !buildWorkflowRunId || !/^[0-9a-f]{64}$/.test(artifactSha256) || !/^[0-9a-f]{64}$/.test(sbomSha256)) {
      return json({ error: "invalid attestation payload", blocked: true }, 400);
    }
    if (!provenanceVerified || !sbomVerified) {
      return json({ error: "both cryptographic verifications required", blocked: true }, 409);
    }
    const { data, error } = await sb.rpc("record_vrs_supply_chain_attestation", {
      p_factory_run_id: factoryRunId,
      p_artifact_sha256: artifactSha256,
      p_github_run_id: identity.run_id,
      p_build_workflow_run_id: buildWorkflowRunId,
      p_provenance_verified: true,
      p_sbom_verified: true,
      p_sbom_sha256: sbomSha256,
      p_evidence: {
        repository: REPOSITORY,
        workflow_ref: identity.workflow_ref,
        attestation_commit_sha: identity.sha,
        attestation_ref: identity.ref,
        source: "github-actions-attestation-v4",
        predicate: "SPDX-2.3",
      },
    });
    if (error) return json({ error: error.message, blocked: true }, 409);
    return json({ ok: true, mandatory: true, result: data, github: identity });
  } catch (e) {
    return json({ error: String((e as Error).message || e), blocked: true }, 401);
  }
});
