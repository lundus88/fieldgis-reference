export function payload() {
  return { ok: true, builder: 'api-service-v1' };
}

Deno.serve(() => new Response(JSON.stringify(payload()), {
  headers: { 'content-type': 'application/json' }
}));
