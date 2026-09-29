# Direct VPS Ingress Deployment — P0

Status: **PREPARED / NON-PRODUCTION / NOT YET DEPLOYED**

Target node: `v103067`  
Runtime identity: `lom-runner`  
Repository: `/home/lom-runner/fieldgis-reference`

This deployment is additive. It must not replace or modify the existing `lom-worker.service`, `lom-heartbeat.service` or `lom-heartbeat.timer`.

## Objective

Establish the canonical VPS-only runtime boundary:

`LOM -> signed task transport -> loopback Secure Task Ingress -> durable queue -> ACP -> VPS runner -> evidence`

The office workstation `BPTSBH-G03-L011` is excluded from the operational dependency graph. There is no workstation failover path.

P0 intentionally stops before public network exposure. ACP handoff remains fail-closed until an authoritative grant loader for `private.agent_capability_grants` is available through an approved least-privilege path.

## Preconditions

- exact reviewed repository revision;
- a fresh 13/13 live VPS canary for authorized node `v103067` is PASS at deployment time;
- `lom-worker.service` and `lom-heartbeat.timer` remain healthy;
- no Production credentials are injected;
- no Docker/sudo/root authority is granted to `lom-runner`;
- rollback is simply stop/disable `lom-secure-ingress.service`.

## Secret bootstrap

As `lom-runner`:

```bash
install -d -m 700 /home/lom-runner/.config/lom
umask 077
python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > /home/lom-runner/.config/lom/ingress-hmac.key
chmod 600 /home/lom-runner/.config/lom/ingress-hmac.key
```

Never print or commit the key.

## Install service

A privileged operator may install only the reviewed unit file:

```bash
sudo install -m 0644 \
  /home/lom-runner/fieldgis-reference/vl/lom-secure-task-ingress-v1/deploy/lom-secure-ingress.service \
  /etc/systemd/system/lom-secure-ingress.service
sudo systemctl daemon-reload
sudo systemctl enable --now lom-secure-ingress.service
```

This one-time administrative action does not grant sudo to `lom-runner`.

## Local verification

```bash
systemctl is-active lom-secure-ingress.service
curl --fail --silent http://127.0.0.1:8765/health
ss -ltnp | grep '127.0.0.1:8765'
```

Required result:
- service active;
- health `READY`;
- listener only on `127.0.0.1:8765`;
- Production locked;
- no listener on `0.0.0.0` or public interface.

## BPTSBH exclusion acceptance

Before classifying the runtime as operational:

- no LOM worker/service/timer is required on `BPTSBH-G03-L011`;
- no LOM runtime secret or queue is stored there;
- no heartbeat or evidence source depends on that workstation;
- no scheduled task on that workstation is required for VPS continuity;
- loss or shutdown of that workstation leaves VPS health and bounded execution unchanged.

Any dependency on the office workstation is a deployment failure, not a fallback condition.

## Stop conditions

Immediately HOLD if:
- listener is public;
- secret file is group/world-readable;
- worker or heartbeat regresses;
- live canary becomes stale/failed;
- any Production credential appears;
- ACP grant resolution is unavailable or ambiguous.

## Next gate

Do not expose this ingress externally yet.

The next implementation gate is a least-privilege authoritative grant resolver for ACP persisted grants plus a secure transport path from LOM to this loopback listener. That change must preserve:
- caller-supplied grants forbidden;
- Production HUMAN_ONLY;
- protected-main merge HUMAN_ONLY;
- connector execution disabled;
- audit/evidence continuity.
