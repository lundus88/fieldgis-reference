# LD Ready Business Kit P2 — First Customer Readiness & Scale Test

Status: DEVELOPMENT / NON-PRODUCTION

## Objective

Prepare the Ready Business Kit for the first real customer while proving the delivery pattern can be repeated across a synthetic 10-client batch.

## Flow

**Lead source → consent → onboarding → client project → clone manifest → delivery queue → human commercial gates → delivery prep**

## P2 components

### 1. Client intake package
Adds:
- acquisition source
- explicit contact consent
- package selection
- P1 client project

No consent means HOLD.

### 2. Clone manifest
A customer project can generate a deterministic tenant/configuration manifest without rebuilding from zero.

The clone manifest:
- does not embed secrets;
- does not embed credentials;
- has payment disabled;
- leaves the client domain unbound;
- keeps Production locked;
- requires human publish authority.

### 3. Capacity governor
Delivery planning is parameterized by:
- daily limit;
- concurrent limit.

It produces queue assignments and exposes capacity bottlenecks instead of silently overbooking.

### 4. Synthetic 10-client simulation
CI creates 10 synthetic customers using the three P0 vertical fixtures.

The simulation proves:
- 10 unique project IDs;
- 10 unique tenant IDs;
- no live customers;
- no revenue evidence;
- zero payment transactions;
- zero Production deployments;
- all Production states locked.

The default fixture uses 3 projects/day and 1 concurrent project to expose queue behavior. These are simulation assumptions, not approved LD commercial capacity.

## First-customer posture

P2 prepares the engineering and delivery process only.

Before the first real paid customer, authoritative commercial/activation gates must still be satisfied separately.

## Human gates retained

- final price
- discount
- quotation/customer release
- customer commitment
- payment activation
- Production publish
- protected-main merge
