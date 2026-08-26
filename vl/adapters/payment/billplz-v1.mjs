import crypto from 'node:crypto';

function canonicalKey(key) {
  return String(key).replace(/[\[\]]/g, '');
}

export function canonicalizeXSignatureParams(params) {
  const entries = [];
  for (const [key, raw] of Object.entries(params || {})) {
    if (key === 'x_signature' || key === 'billplz[x_signature]') continue;
    const value = raw == null ? '' : String(raw);
    entries.push(`${canonicalKey(key)}${value}`);
  }
  entries.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  return entries.join('|');
}

export function computeXSignature(params, xSignatureKey) {
  if (!xSignatureKey) throw new Error('BILLPLZ_X_SIGNATURE_KEY required');
  return crypto
    .createHmac('sha256', xSignatureKey)
    .update(canonicalizeXSignatureParams(params), 'utf8')
    .digest('hex');
}

export function verifyXSignature(params, xSignatureKey) {
  const received = String(params?.x_signature || params?.['billplz[x_signature]'] || '');
  if (!received) return false;
  const expected = computeXSignature(params, xSignatureKey);
  if (received.length !== expected.length) return false;
  return crypto.timingSafeEqual(Buffer.from(received), Buffer.from(expected));
}

export function normalizeBillStatus(payload) {
  const paid = String(payload?.paid ?? '').toLowerCase() === 'true';
  const state = String(payload?.state || '').toLowerCase();
  const tx = String(payload?.transaction_status || '').toLowerCase();
  if (paid && state === 'paid' && (!tx || tx === 'completed')) return 'paid';
  if (state === 'deleted') return 'cancelled';
  if (tx === 'failed') return 'failed';
  return 'pending';
}

export function validateAuthoritativeCallback({ payload, xSignatureKey, order }) {
  if (!verifyXSignature(payload, xSignatureKey)) {
    return { ok: false, reason: 'invalid_signature' };
  }
  const expectedAmount = Number(order?.amount_minor);
  const actualAmount = Number(payload?.amount);
  if (!Number.isInteger(expectedAmount) || expectedAmount < 1) {
    return { ok: false, reason: 'invalid_server_order_amount' };
  }
  if (actualAmount !== expectedAmount) {
    return { ok: false, reason: 'amount_mismatch' };
  }
  if (String(order?.currency || '').toUpperCase() !== 'MYR') {
    return { ok: false, reason: 'unsupported_currency' };
  }
  if (order?.provider_bill_id && String(order.provider_bill_id) !== String(payload?.id || '')) {
    return { ok: false, reason: 'provider_bill_id_mismatch' };
  }
  return {
    ok: true,
    provider_bill_id: String(payload?.id || ''),
    status: normalizeBillStatus(payload),
    paid_amount_minor: Number(payload?.paid_amount || 0),
    transaction_id: payload?.transaction_id ? String(payload.transaction_id) : null,
  };
}

export function idempotencyKey(payload) {
  const bill = String(payload?.id || '');
  const tx = String(payload?.transaction_id || '');
  const state = normalizeBillStatus(payload);
  return `billplz:${bill}:${tx || 'no-tx'}:${state}`;
}

export function decideFulfillment({ previousStatus, callbackStatus }) {
  if (previousStatus === 'paid') {
    return { apply: false, reason: 'already_paid' };
  }
  if (callbackStatus !== 'paid') {
    return { apply: false, reason: 'not_paid' };
  }
  return { apply: true, reason: 'verified_paid_transition' };
}
