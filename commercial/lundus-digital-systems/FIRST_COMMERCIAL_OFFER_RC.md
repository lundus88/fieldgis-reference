# First Commercial Offer RC

Status: PROPOSED — human approval required before OFFER_LOCKED becomes YES.

## Primary launch offer
**Custom Digital Systems & Automation — Quotation-Led Implementation**

Customer promise:
Design and implement a focused digital workflow or operational system with an agreed scope, acceptance criteria and delivery boundary.

## Why this is the primary launch offer
- fits the LUNDUS DIGITAL SYSTEMS umbrella without exposing internal VL/LOM architecture;
- can be sold before individual SaaS products are broadly public-ready;
- supports human-approved, customer-specific pricing rather than invented public prices;
- maps directly to the Commercial Golden Transaction and customer-scoped payment offer model.

## Commercial method
1. Enquiry received.
2. Lead qualified.
3. Scope and deliverables defined.
4. Human-approved quotation issued.
5. A customer-specific commercial offer is created with:
   - offer_type = customer_quote
   - customer_account_id
   - exact approved amount
   - MYR currency
   - valid_until
   - fulfillment_mode
6. Customer accepts terms.
7. Checkout link is created from the server-authoritative offer.
8. Signed backend callback changes payment state.
9. Fulfilment remains a separate controlled action.
10. Delivery and close are recorded.

## Pricing posture
No public fixed price is invented in this RC.
The approved quotation is the authoritative commercial amount.

## Secondary launch-facing service lines
- AI-Assisted SaaS & Decision Support
- Geospatial & Mapping Systems

These remain quotation/enquiry routes unless a separate product offer is explicitly approved.

## Scope boundary
This offer does not imply:
- automatic production deployment;
- access to government databases;
- professional/statutory approval;
- uncontrolled AI decision authority;
- customer charging before the payment gate is authorised.

## Human gate
To set OFFER_LOCKED = YES, approve:
1. this primary offer name/scope;
2. quotation-led pricing method;
3. the rule that only human-approved customer quotes may become active customer_quote offers.
