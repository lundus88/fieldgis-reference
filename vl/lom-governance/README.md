# LOM Governance Registry P0

This directory defines authoritative ownership metadata for LOM capabilities.

Core rule:

`one capability -> one authoritative owner -> many consumers`

Before a new capability is built, consumers must query the registry and follow:

`reuse -> extend -> integrate -> build only on proven gap`

The registry is governance metadata only. It does not introduce a second CRM, payment, accounting, order, QA, analytics, referral, HR or audit engine.


## Cross-cutting doctrine

`LONG_TERM_EXECUTION_DOCTRINE.md` defines the approved LOM long-term execution decision filter. It is policy overlay only and must follow the registry rule:

`reuse -> extend -> integrate -> build only on proven gap`

It must not create duplicate capabilities or widen execution authority.
