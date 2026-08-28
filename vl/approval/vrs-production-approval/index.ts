import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || Deno.env.get("SUPABASE_PUBLISHABLE_KEY") || "";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json" },
});

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "POST required" }, 405);

  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ")) return json({ error: "Bearer token required" }, 401);

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }

  const deploymentId = String(body?.deployment_id || "").trim();
  const rationale = String(body?.rationale || "").trim();

  if (!/^[0-9a-fA-F-]{36}$/.test(deploymentId)) {
    return json({ error: "valid deployment_id required" }, 400);
  }
  if (!rationale) return json({ error: "rationale required" }, 400);

  const headers = new Headers({
    Authorization: auth,
    "Content-Type": "application/json",
  });
  if (ANON_KEY) headers.set("apikey", ANON_KEY);

  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/rpc/approve_vrs_production_release`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        p_deployment_id: deploymentId,
        p_rationale: rationale,
      }),
    },
  );

  const text = await response.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    return json({ error: "approval_failed", details: data }, response.status);
  }

  return json({ ok: true, approval: data, deployment_id: deploymentId });
});
