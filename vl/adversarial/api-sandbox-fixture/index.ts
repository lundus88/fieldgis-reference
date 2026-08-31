import { encodeBase64 } from 'jsr:@std/encoding/base64';

export function payload() {
  return { ok: true, builder: 'api-service-v1', encoded: encodeBase64('sandbox') };
}

Deno.serve(() => new Response(JSON.stringify(payload()), {
  headers: { 'content-type': 'application/json' }
}));
