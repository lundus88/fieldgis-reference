# Commercial Fulfilment, Receipt & Close RC

Status: REVIEW CANDIDATE ONLY
Production application: NOT AUTHORISED

## Purpose
Close the post-payment part of the Commercial Golden Transaction without allowing a paid callback to auto-deliver a service.

## Fulfilment authority
A commercial order can be fulfilled only when:
- the caller is authenticated;
- AAL2 MFA is present;
- the caller has owner/admin role;
- environment is production and purpose is commercial_order;
- order status is paid and paid_at exists;
- fulfilment state is unfulfilled;
- a valid signed paid Billplz webhook exists for the same provider bill and amount;
- an idempotent action key is supplied;
- a receipt reference is issued;
- delivery evidence is recorded.

## Documents
A receipt record is mandatory for fulfilment.
An invoice reference may also be recorded when applicable.

The ledger deliberately sets tax_einvoice_claim=false. These records must not be represented as a Malaysian tax e-Invoice or statutory tax document unless a separately verified compliance flow authorises that claim.

## Close
An order may be closed only after:
- paid status;
- fulfilled state;
- issued receipt evidence;
- fulfilled event evidence;
- AAL2 owner/admin approval.

## Safety
- no browser-controlled fulfilment;
- no payment callback auto-fulfilment;
- no anonymous execution;
- no tax/e-Invoice claim;
- no Production migration applied by this RC.
