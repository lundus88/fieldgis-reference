# LOM Secure Task Ingress v1

Status: **DRAFT / NON-PRODUCTION / NOT DEPLOYED**

Purpose: remove the office workstation from the normal LOM execution path by adding an authenticated, bounded task buffer in front of the existing ACP and VPS executor.

Target path:

`Chat/LOM -> signed ingress envelope -> bounded buffer -> ACP policy gate -> VPS runner -> evidence journal -> result`

## Reuse, not duplication

This component does **not** create a second authority engine or executor.

- ACP remains the policy authority.
- `VPSBodyExecutorAdapter` remains the bounded BodyRuntime bridge.
- `runner.py` remains the node task validator/executor.
- existing evidence journals remain authoritative for execution evidence.
- the ingress only authenticates and buffers already-bounded work.

## Security invariants

- fail closed;
- HMAC signature required; secret is runtime-supplied and never stored in the repository;
- no self-grant or root-grant issuance;
- production remains locked;
- connector capabilities are rejected at ingress v1;
- only registered PREPARE-level body actions are accepted;
- exact project scope binding;
- task expiry and maximum TTL enforced;
- deterministic idempotency key binding;
- identical replay is idempotent;
- changed replay is denied;
- bounded queue capacity;
- no arbitrary shell, URL, token, secret, credential or script field;
- ingress never executes a task directly.

## Current deployment posture

Repository code only. The live VPS baseline remains unchanged and pinned to the approved PR #396 revision. No systemd unit, port, firewall rule, secret, public endpoint, DNS, Supabase migration, or Production configuration is changed by this PR.

A later deployment must use a dedicated secret delivery mechanism, bind to a private/local interface by default, and prove ACP + executor + evidence end-to-end before any external task intake is enabled.
