import { writeFileSync } from 'node:fs';

const leaked = Boolean(
  process.env.VRS_OIDC_TOKEN ||
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN ||
  process.env.ACTIONS_ID_TOKEN_REQUEST_URL
);
writeFileSync('.vl-gis-sandbox-env.json', JSON.stringify({ leaked }, null, 2));

export default { build: { outDir: 'dist' } };
