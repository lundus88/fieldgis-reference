import assert from 'node:assert/strict';
import {
  canonicalizeXSignatureParams,
  computeXSignature,
  verifyXSignature,
  normalizeBillStatus,
  validateAuthoritativeCallback,
  idempotencyKey,
  decideFulfillment,
} from './billplz-v1.mjs';

const key='S-s7b4yWpp9h7rrkNM1i3Z_g';

// Official Billplz X Signature redirect fixture (reproducible, no redacted fields).
const redirectFixture={
  'billplz[id]':'zq0tm2wc',
  'billplz[paid]':'true',
  'billplz[paid_at]':'2018-09-27 15:15:09 +0800',
  'billplz[x_signature]':'4aab095fe5a39b1d534500988f9a0cb085cd1b6d5bbb55dd4e02ea6fa102b47b',
};
assert.equal(computeXSignature(redirectFixture,key),redirectFixture['billplz[x_signature]']);
assert.equal(verifyXSignature(redirectFixture,key),true);

// Deterministic callback fixture signed locally using the documented HMAC-SHA256 algorithm.
const callback={
  id:'vltest001',
  collection_id:'vlcollection',
  paid:'true',
  state:'paid',
  amount:'100',
  paid_amount:'100',
  due_at:'2026-08-27',
  email:'payer@example.test',
  mobile:'',
  name:'VL TEST',
  url:'https://www.billplz-sandbox.com/bills/vltest001',
  paid_at:'2026-08-27 10:00:00 +0800',
};
callback.x_signature=computeXSignature(callback,key);
assert.equal(verifyXSignature(callback,key),true);
assert.equal(normalizeBillStatus(callback),'paid');

const auth=validateAuthoritativeCallback({
  payload:callback,
  xSignatureKey:key,
  order:{amount_minor:100,currency:'MYR',provider_bill_id:'vltest001'}
});
assert.equal(auth.ok,true);
assert.equal(auth.status,'paid');

const tampered={...callback,amount:'999'};
assert.equal(verifyXSignature(tampered,key),false,'tampered amount must invalidate signature');

const correctlySignedWrongAmount={...callback,amount:'999'};
correctlySignedWrongAmount.x_signature=computeXSignature(correctlySignedWrongAmount,key);
assert.deepEqual(
  validateAuthoritativeCallback({payload:correctlySignedWrongAmount,xSignatureKey:key,order:{amount_minor:100,currency:'MYR',provider_bill_id:'vltest001'}}),
  {ok:false,reason:'amount_mismatch'}
);

assert.deepEqual(
  validateAuthoritativeCallback({payload:callback,xSignatureKey:key,order:{amount_minor:100,currency:'USD',provider_bill_id:'vltest001'}}),
  {ok:false,reason:'unsupported_currency'}
);

assert.equal(idempotencyKey(callback),'billplz:vltest001:no-tx:paid');
assert.deepEqual(decideFulfillment({previousStatus:'paid',callbackStatus:'paid'}),{apply:false,reason:'already_paid'});
assert.deepEqual(decideFulfillment({previousStatus:'pending',callbackStatus:'failed'}),{apply:false,reason:'not_paid'});
assert.deepEqual(decideFulfillment({previousStatus:'pending',callbackStatus:'paid'}),{apply:true,reason:'verified_paid_transition'});
assert.equal(canonicalizeXSignatureParams({b:'2',a:'1',x_signature:'ignored'}),'a1|b2');

console.log(JSON.stringify({status:'PASS',tests:'official-signature-fixture,callback-signature,tamper,status,amount,currency,idempotency,fulfillment'},null,2));
