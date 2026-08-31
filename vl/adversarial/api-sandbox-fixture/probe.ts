const sensitive = [
  'VRS_OIDC_TOKEN',
  'SUPABASE_SERVICE_ROLE_KEY',
  'ACTIONS_ID_TOKEN_REQUEST_TOKEN',
  'ACTIONS_ID_TOKEN_REQUEST_URL'
];
const visible = sensitive.filter((name) => Boolean(Deno.env.get(name)));
await Deno.writeTextFile(
  '/workspace/.vl-api-sandbox-env.json',
  JSON.stringify({ leaked: visible.length > 0, visible })
);
if (visible.length > 0) throw new Error(`credential leak: ${visible.join(',')}`);
