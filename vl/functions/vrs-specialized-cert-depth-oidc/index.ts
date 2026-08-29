import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.2.10";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ISSUER = "https://token.actions.githubusercontent.com";
const AUDIENCE = "vrs-specialized-cert-depth";
const REPOSITORY = "lundus88/fieldgis-reference";
const WORKFLOW_REF = "lundus88/fieldgis-reference/.github/workflows/vl-specialized-cert-depth.yml@refs/heads/main";
const MAIN_REF = "refs/heads/main";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const sb = createClient(SUPABASE_URL, SERVICE_ROLE, { auth: { persistSession: false } });

const REQUIRED: Record<string,string[]> = {
  "gis-web-v1": ["static_analysis_pass","map_runtime_pass","gps_marker_pass","export_kml_pass"],
  "mobile-flutter-v1": ["static_analysis_pass","test_pass","apk_build_pass","android_device_e2e_pass","gps_capture_pass"],
  "api-service-v1": ["api_compile_test","auth_http_e2e","data_api_http_e2e","database_security","qa_regression","rollback_contract"],
};
const API_DB_GATES = ["api_compile_test","database_security","qa_regression","rollback_contract"];
const J = (body: unknown, status=200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

async function verifyOidc(token: string) {
  const { payload } = await jwtVerify(token, JWKS, { issuer: ISSUER, audience: AUDIENCE, algorithms: ["RS256"], clockTolerance: 60 });
  const workflowRef = String(payload.job_workflow_ref || payload.workflow_ref || "");
  if (payload.repository !== REPOSITORY || payload.ref !== MAIN_REF || workflowRef !== WORKFLOW_REF) throw new Error("OIDC identity not allowed");
  return {
    run_id: String(payload.run_id || ""), run_attempt: String(payload.run_attempt || ""),
    job_workflow_ref: workflowRef, sha: String(payload.sha || ""), actor: String(payload.actor || "")
  };
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return J({ error: "POST required" }, 405);
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ")) return J({ error: "GitHub OIDC bearer token required" }, 401);
  try {
    const identity = await verifyOidc(auth.slice(7));
    const body = await req.json().catch(() => ({}));
    const builder = String(body.builder_key || "");
    const required = REQUIRED[builder];
    if (!required) return J({ error: "builder not allowed", blocked: true }, 400);
    const passed = Array.isArray(body.passed_evidence) ? body.passed_evidence.map(String).sort() : [];
    if (JSON.stringify(passed) !== JSON.stringify([...required].sort())) return J({ error: "evidence set mismatch", blocked: true, required }, 400);

    const { data: runs, error: runErr } = await sb.from("factory_runs")
      .select("id,project_id,input,created_at,state,target_environment,production_locked")
      .eq("target_environment", "staging").eq("production_locked", true).eq("state", "awaiting_approval")
      .order("created_at", { ascending: true });
    if (runErr) throw runErr;

    let target: any = null;
    for (const r of runs || []) {
      const input = (r.input || {}) as Record<string,unknown>;
      if (input.builder_key !== builder || input.certification_depth_run !== true) continue;
      const { data: ev, error: evErr } = await sb.from("builder_certification_evidence")
        .select("evidence_type").eq("builder_key", builder).eq("factory_run_id", r.id).in("evidence_type", required);
      if (evErr) throw evErr;
      const have = new Set((ev || []).map((x:any) => String(x.evidence_type)));
      if (required.some(x => !have.has(x))) { target = r; break; }
    }
    if (!target) return J({ ok: true, status: "no_work", builder_key: builder, identity });

    if (builder === "api-service-v1") {
      const { data: gates, error: gateErr } = await sb.from("release_gates").select("gate_key,status")
        .eq("factory_run_id", target.id).in("gate_key", API_DB_GATES);
      if (gateErr) throw gateErr;
      const map = new Map((gates || []).map((g:any) => [String(g.gate_key), String(g.status)]));
      const missing = API_DB_GATES.filter(k => map.get(k) !== "pass");
      if (missing.length) return J({ error: "API prerequisite release gates not PASS", blocked: true, missing, factory_run_id: target.id }, 409);
    }

    const sourceUri = `https://github.com/${REPOSITORY}/actions/runs/${identity.run_id}#attempt-${identity.run_attempt || "1"}`;
    const rows = required.map((evidence_type) => ({
      builder_key: builder, factory_run_id: target.id, project_id: target.project_id,
      evidence_type, evidence_status: "pass",
      evidence: { provider: "github_actions_oidc", source: "specialized_builder_depth", github_run_id: identity.run_id,
        github_run_attempt: identity.run_attempt || "1", github_sha: identity.sha, workflow_ref: identity.job_workflow_ref,
        runtime_tested: true, api_release_gate_prerequisites_verified: builder === "api-service-v1" },
      source_uri: sourceUri,
    }));
    const { error: insErr } = await sb.from("builder_certification_evidence").insert(rows);
    if (insErr) throw insErr;
    const { data: evaluation, error: evalErr } = await sb.rpc("evaluate_builder_certification", { p_builder_key: builder, p_activate: false });
    if (evalErr) throw evalErr;
    return J({ ok: true, status: "recorded", builder_key: builder, factory_run_id: target.id, evidence_types: required, identity, certification: evaluation });
  } catch (e) {
    return J({ error: String((e as Error).message || e), blocked: true }, 401);
  }
});
