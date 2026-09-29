# LOM Virtual World — Shared Contracts & Golden Transaction v1

Status: DRAFT / NON-PRODUCTION  
Date: 2026-09-29

## 1. Purpose

Turn the Virtual World concept into an implementable P0 contract without building duplicate engines.

The P0 release must prove one end-to-end economic journey using existing LOM, LD, LundusLead, LOM Education and payment/accounting adapters.

## 2. Canonical IDs

All participating systems must preserve stable cross-system identifiers:

- member_id
- business_id
- skill_profile_id
- opportunity_id
- offer_id
- order_id
- payment_reference_id
- delivery_id
- acceptance_id
- earning_id
- reputation_event_id
- dispute_id
- audit_event_id

IDs must be immutable once issued. Display names may change; identifiers must not.

## 3. Event envelope

Every domain event should contain at minimum:

```json
{
  "event_id": "evt_*",
  "event_type": "domain.action",
  "occurred_at": "ISO-8601",
  "actor_id": "member/system/service identifier",
  "subject_id": "primary entity identifier",
  "source_system": "authoritative producing system",
  "correlation_id": "journey/order/workflow trace",
  "evidence_ref": "immutable or verifiable evidence reference",
  "policy_version": "policy applied",
  "authority_context": "grant/role/human-gate context"
}
```

## 4. P0 Golden World Transaction

The first Preview proof must execute this exact chain:

1. **Member registered**
2. **Identity assurance recorded**
3. **Skill or need profile created**
4. **Opportunity matched**
5. **Offer accepted**
6. **Order created**
7. **Payment confirmed by lawful payment adapter**
8. **Work/product delivered**
9. **Buyer acceptance recorded**
10. **Earning/commission ledger updated**
11. **Reputation evidence updated**
12. **Repeat/referral opportunity generated**
13. **All events visible in audit trace**

## 5. System ownership

| Responsibility | Canonical owner |
|---|---|
| Member identity, policy, authority, audit | LOM Core |
| Opportunity acquisition/matching inputs | LundusLead / Economic Participation Network |
| Skills and learning | LOM Education |
| Catalogue, offer, order, delivery, acceptance | LD Commerce / Product Factory |
| Payment confirmation | Payment Adapter |
| Accounting evidence | Accounting Adapter |
| Earnings, commissions, budget evidence | Treasury Ledger |
| Trust, reputation, dispute | LOM Trust layer |

No subsystem may silently become authoritative for another subsystem's domain.

## 6. Hard gates

The transaction must fail closed when:
- member authority is unresolved;
- payment evidence is missing or contradictory;
- delivery evidence is absent where required;
- beneficiary identity is ambiguous;
- a high-risk action requires human approval and has not received it;
- the requested activity is outside platform policy or legal boundary.

## 7. Human gates

Mandatory human review for:
- production activation;
- high-value or anomalous payouts;
- irreversible account restrictions;
- policy exceptions;
- legal/regulatory representations;
- disputed high-value transactions;
- authority elevation;
- release of sensitive data.

## 8. Preview acceptance criteria

P0 is ready for controlled pilot only when:
- all 13 Golden World steps complete on Preview;
- every step emits traceable evidence;
- cross-user isolation is tested;
- payment data is not fabricated or manually asserted as confirmed;
- one dispute path is tested;
- one refund/cancellation path is tested;
- one failed transaction is tested;
- one repeat/referral loop is tested;
- no production deployment occurs automatically.

## 9. P0 metrics

Minimum dashboard:
- registered members;
- activated members;
- qualified opportunities;
- offers accepted;
- paid orders;
- gross transaction value;
- LOM revenue;
- member earnings;
- contribution margin;
- median delivery time;
- acceptance rate;
- repeat/referral rate;
- dispute/refund rate;
- fraud/abuse incidents;
- time-to-economic-outcome.

## 10. Build order

1. Shared IDs + event registry
2. Identity/profile adapter
3. Opportunity adapter
4. Offer/order contract
5. Payment confirmation adapter
6. Delivery/acceptance contract
7. Earnings/commission ledger
8. Reputation evidence
9. Dispute flow
10. Unified audit trace
11. Preview Golden World Transaction
12. Security/privacy/commercial review
13. Human decision on controlled pilot

## 11. Non-goals

P0 does not include:
- sovereign-state functions;
- legal citizenship/passports;
- state taxation;
- deposit-taking;
- independent lending;
- legal-tender currency;
- cryptocurrency/token issuance;
- statutory licences;
- legal land title;
- autonomous adjudication without appeal;
- duplicate CRM/LMS/payment engines.
