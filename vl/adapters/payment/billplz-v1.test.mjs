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
const callback={
  id:'zq0tm2wc',
  collection_id:'yhx5t1pp',
  paid:'true',
  state:'paid',
  amount:'100',
  paid_amount:'100',
  due_at:'2018-9-27',
  email:'[email protected]',
  mobile:'',
  name:'TESTER',
  url:'http://www.billplz-sandbox.com/bills/zq0tm2wc',
  paid_at:'2018-09-27 15:15:09 +0800',
  x_signature:'0fe0a20b8d557eeae570377783d062a3816a9ea80f368860bacfa7ec3ca4d00e',
};

assert.equal(
  computeXSignature(callback,key),
  callback.x_signature,
  'official Billplz X Signature fixture must verify'
);
assert.equal(verifyXSignature(callback,key),true);
assert.equal(normalizeBillStatus(callback),'paid');

const auth=validateAuthoritativeCallback({
  payload:callback,
  xSignatureKey:key,
  order:{amount_minor:100,currency:'MYR',provider_bill_id:'zq0tm2wc'}
});
assert.equal(auth.ok,true);
assert.equal(auth.status,'paid');

const tampered={...callback,amount:'999'};
assert.equal(verifyXSignature(tampered,key),false,'tampered amount must invalidate signature');

const correctlySignedWrongAmount={...callback,amount:'999'};
correctlySignedWrongAmount.x_signature=computeXSignature(correctlySignedWrongAmount,key);
assert.deepEqual(
  validateAuthoritativeCallback({payload:correctlySignedWrongAmount,xSignatureKey:key,order:{amount_minor:100,currency:'MYR',provider_bill_id:'zq0tm2wc'}}),
  {ok:false,reason:'amount_mismatch'}
);

const invalidCurrency={...callback};
assert.deepEqual(
  validateAuthoritativeCallback({payload:invalidCurrency,xSignatureKey:key,order:{amount_minor:100,currency:'USD',provider_bill_id:'zq0tm2wc'}}),
  {ok:false,reason:'unsupported_currency'}
);

assert.equal(idempotencyKey(callback),'billplz:zq0tm2wc:no-tx:paid');
assert.deepEqual(decideFulfillment({previousStatus:'paid',callbackStatus:'paid'}),{apply:false,reason:'already_paid'});
assert.deepEqual(decideFulfillment({previousStatus:'pending',callbackStatus:'failed'}),{apply:false,reason:'not_paid'});
assert.deepEqual(decideFulfillment({previousStatus:'pending',callbackStatus:'paid'}),{apply:true,reason:'verified_paid_transition'});

const canonical=canonicalizeXSignatureParams({b:'2',a:'1',x_signature:'ignored'});
assert.equal(canonical,'a1|b2');

console.log(JSON.stringify({status:'PASS',tests:'signature,status,amount,currency,idempotency,fulfillment'},null,2));
