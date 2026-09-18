# LUNDUS DIGITAL SYSTEMS — Commercial Golden Transaction Dry Run

Status: NON-PRODUCTION MODEL TEST

This dry run validates the intended commercial state machine without charging a customer or mutating Production.

## Modelled path
Lead / enquiry
-> human qualification
-> human-approved quotation
-> customer-scoped offer
-> server-authoritative amount
-> pending order
-> provider bill
-> signed paid callback
-> payment confirmation notification
-> AAL2 owner/admin fulfilment
-> receipt evidence
-> fulfilment notification
-> explicit close
-> close notification

## Negative paths tested
- wrong customer cannot use another customer's quote
- expired quote is blocked
- browser-supplied amount cannot alter server-authoritative price
- duplicate provider bill attachment is blocked
- invalid payment signature is blocked
- amount mismatch is blocked
- duplicate webhook is idempotent
- payment confirmation does not auto-fulfil
- fulfilment without AAL2 is blocked
- fulfilment without delivery evidence is blocked
- unpaid fulfilment is blocked
- unpaid payment-confirmed notification is blocked

## Important limitation
A PASS here means the intended state-machine contract is internally coherent. It is **not** proof that Billplz, Resend, LundusLead, Supabase, Vercel or the public website are integrated in Production.

Therefore:
- GOLDEN_TRANSACTION_DRY_RUN = PASS when CI succeeds
- GOLDEN_TRANSACTION_PASS = HOLD until one controlled real paid transaction is reconciled end-to-end
