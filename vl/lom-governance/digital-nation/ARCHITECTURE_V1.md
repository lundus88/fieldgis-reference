# LOM Digital Nation — Architecture v1

Status: DRAFT / NON-PRODUCTION ARCHITECTURE  
Date: 2026-09-29  
Owner: LOM Core Architecture

## 1. Architecture objective

Implement LOM Digital Nation primarily as an orchestration layer across existing LOM capabilities. Avoid duplicate CRM, payment, identity, education, marketplace, workflow or domain engines.

## 2. Logical stack

```text
Experience Layer
  └─ Enter LOM Nation / Member Portal / Mobile UX

Member Layer
  ├─ LOM Member ID
  ├─ Profile
  ├─ Consent & Privacy
  ├─ Skill Graph
  └─ Reputation Signals

Opportunity & Growth Layer
  ├─ LundusLead
  ├─ Content-to-Lead
  ├─ Affiliate / Referral
  └─ Opportunity Discovery

Learning Layer
  └─ LOM Education

Economic Layer
  ├─ Service / Product Catalogue
  ├─ Product Factory
  ├─ Marketplace Composition
  ├─ Quotation / Checkout
  ├─ Payment
  ├─ Invoice / Receipt / Accounting
  ├─ Delivery
  └─ Acceptance / Repeat / Referral

Civic & Domain Layer
  ├─ UrusMY
  ├─ SabahLot
  ├─ e-BKL SurveyOS
  ├─ SLP / GFVE
  └─ future governed domain systems

LOM Core Control Plane
  ├─ Policy
  ├─ Authority / Human Gate
  ├─ Orchestration
  ├─ Evidence
  ├─ Audit
  ├─ Security
  ├─ Memory / World State
  └─ Analytics & Optimization

Adapter Layer
  ├─ Payment
  ├─ Accounting
  ├─ Email / Messaging
  ├─ AI models
  ├─ Storage
  └─ External lawful services
```

## 3. Canonical member journey

```text
Enter
→ Create/Sign in to Member Profile
→ Consent & Identity Assurance
→ Skill/Need/Goal Profile
→ Learn or Discover Opportunity
→ Qualification
→ Offer / Service / Product
→ Transaction
→ Work / Production
→ QA / Human Gate where required
→ Delivery
→ Acceptance
→ Reputation Evidence
→ Repeat / Referral / Upsell
→ Economic Analytics
```

## 4. Core data domains

P0 should define stable IDs for:
- member;
- organization/business;
- skill;
- credential;
- opportunity;
- offer;
- product/service;
- order;
- payment reference;
- delivery;
- acceptance;
- referral/affiliate attribution;
- evidence;
- dispute;
- reputation event;
- consent record;
- policy decision;
- audit event.

Personally identifying data, reputation data and public profile data must remain logically separable.

## 5. Authority model

Every action should resolve:
1. actor identity;
2. requested capability;
3. policy;
4. grant/role;
5. risk level;
6. evidence requirements;
7. human gate requirement;
8. audit record.

The system must fail closed when authority is ambiguous for consequential actions.

## 6. P0 interface set

Initial product surfaces:

### A. Enter LOM Nation
- clear non-sovereign positioning;
- value proposition;
- join/sign-in;
- marketplace and learning discovery.

### B. Member Home
- profile;
- skill progress;
- opportunities;
- active orders/work;
- earnings/revenue evidence where applicable;
- referrals;
- notifications;
- privacy controls.

### C. Opportunity Board
- jobs/gigs;
- projects;
- affiliate opportunities;
- products to sell;
- learning paths leading to opportunity.

### D. Marketplace
- existing LD products/services;
- LOM Education products;
- governed domain offerings;
- transparent pricing and delivery terms.

### E. Trust Center
- identity status;
- transaction evidence;
- reputation explanations;
- disputes;
- consent;
- security notices.

### F. Economic Dashboard
- leads;
- conversions;
- GMV/revenue;
- commissions;
- delivery time;
- repeat rate;
- referral rate;
- disputes/refunds;
- contribution margin.

## 7. P0 reuse map

No new standalone engine is required for:
- lead generation — reuse LundusLead;
- website/product generation — reuse Product Factory;
- transaction flow — reuse Commerce/Golden Transaction;
- education — reuse LOM Education;
- civic workflows — reuse UrusMY;
- geospatial/cadastral workflows — reuse existing domain systems;
- governance/audit — reuse LOM Core;
- accounting/payments — reuse adapters.

Only thin composition services and shared contracts should be introduced where required.

## 8. Security baseline

Mandatory:
- least privilege;
- tenant/member isolation;
- encrypted secrets;
- server-side authorization;
- auditable changes;
- anti-fraud controls;
- rate limiting;
- abuse reporting;
- recovery procedures;
- explicit production gates;
- no office-device dependency for canonical LOM runtime.

## 9. P0 implementation sequence

1. Freeze Charter and Architecture v1 in draft.
2. Define shared IDs and event contracts.
3. Compose Member Profile from existing identity/entitlement foundations.
4. Connect LundusLead opportunity acquisition.
5. Connect LD catalogue and Golden Transaction.
6. Connect LOM Education skill/learning path.
7. Add affiliate/referral attribution.
8. Add evidence-backed reputation events.
9. Build Member Home + Opportunity Board + Marketplace shell.
10. Execute one end-to-end Golden Citizen Journey in Preview.
11. Security, privacy, financial and policy review.
12. Human decision on controlled pilot.

## 10. Golden Citizen Journey

The release test is:

**New member → profile → learning/skill signal → matched opportunity → accepted offer → lawful payment → work/delivery → customer acceptance → commission/earnings record → reputation evidence → repeat/referral.**

Every transition must produce sufficient audit evidence.

## 11. P0 exclusions

Do not build in P0:
- sovereign-government claims;
- passports or legally misleading citizenship documents;
- independent fiat currency;
- cryptocurrency/token issuance;
- deposit-taking;
- investment products;
- voting systems presented as governmental elections;
- duplicate CRM;
- duplicate LMS;
- duplicate payment processor;
- uncontrolled autonomous sanctions;
- production launch without explicit human approval.

## 12. Initial metrics

Primary:
- activated members;
- active economic participants;
- qualified opportunities;
- paid transactions;
- repeat transaction rate;
- member-earned income through the ecosystem;
- LOM revenue and contribution margin;
- delivery time;
- dispute/refund rate;
- affiliate/referral conversion.

North-star operational measure:

**Time from qualified member intent to verified useful economic outcome.**


## 13. Advanced society control loop

The architecture must support all twelve advanced-society fundamentals through existing owners and thin composition layers.

Canonical institutional loop:

```text
Charter / Policy
→ Identity / Authority
→ Education / Skill
→ Market / Business / Work
→ Payment / Treasury / Accounting
→ Delivery / Acceptance
→ Trust / Rights / Appeal
→ Statistics / Measurement
→ Research / Innovation
→ Continuous Improvement
→ Verified Change
```

System maturity is evidence-based:

```text
DEFINED → TESTED → PREVIEW_PROVEN → PILOT_PROVEN → PRODUCTION_PROVEN
```

CI PASS may advance a component to TESTED, but never by itself to PILOT_PROVEN or PRODUCTION_PROVEN.

Detailed mapping: `ADVANCED_SOCIETY_FUNDAMENTALS_V1.md` and `ADVANCED_SOCIETY_IMPLEMENTATION_MATRIX_V1.md`.


## 14. Best-of-World benchmark intake

External national/institutional practices enter LOM through the governed benchmark path:

```text
World evidence
→ Global Nation Benchmark Matrix
→ HVAE
→ duplication/compatibility/risk review
→ security/legal/economic/governance review
→ existing LOM owner
→ Preview/Pilot evidence
→ measured improvement
```

Rules:
- benchmark capabilities, not whole countries;
- no overall country ranking or political-system winner;
- user-nominated country strengths remain hypotheses until verified;
- record source, period, scope, limitations and trade-offs;
- prefer adaptation through existing capabilities;
- production remains a separate human gate.

Canonical references:
- `BEST_OF_WORLD_ARCHITECTURE_V1.md`
- `GLOBAL_NATION_BENCHMARK_MATRIX_V1.md`
- `global-nation-benchmark-v1.json`
- `benchmark-source-registry-v1.json`


## 15. Foundational gap closure

Before expanding more surface area, LOM Virtual World must close eight structural gaps:

### P0
- Persistent World State & Event Runtime
- Economic Bootstrapping & Liquidity
- Jurisdiction & Compliance Router
- Delegated Authority & Permission Wallet

### P1
- Policy Lifecycle & Constitutional Change Control
- Market Fairness & Economic Integrity
- World Simulation & Synthetic Society Sandbox
- Culture, Values & Social Cohesion

Canonical integration:

```text
Identity
→ Authority
→ World State
→ Learn
→ Opportunity
→ Market
→ Transaction
→ Delivery
→ Trust
→ Business
→ Capital / Partner Access where lawful
→ Community
→ Analytics
→ Improvement
```

Reuse bindings:
- world state → Operational Twin World Model + canonical registries/event evidence;
- jurisdiction → LD Global Commerce Readiness;
- delegated authority → Agent Control Plane;
- market fairness → LOM Trust + customer fraud/payment-abuse controls;
- simulation → Golden World Preview + Operational Twin + CI;
- liquidity → Market + LundusLead + Economic Participation + Education + Treasury.

Detailed controls: `FOUNDATIONAL_GAPS_CLOSURE_V1.md`.

Architectural priority now becomes **depth before breadth**: persistence, liquidity, jurisdiction, delegated authority, fairness and simulation must mature before major new feature families are added.
