from pathlib import Path
import json
import sys

RUNBOOK = Path('vl/agent-control-plane/ACP_PRODUCTION_ROLLOUT_RUNBOOK.md').read_text()

checks = {
    'planning only status explicit': 'PLANNING ONLY — NOT APPROVED / NOT APPLIED' in RUNBOOK,
    'separate founder approval checkpoint exists': '# Phase 0 — Founder approval checkpoint' in RUNBOOK,
    'read only preflight exists': '# Phase 1 — Read-only production preflight' in RUNBOOK,
    'store migration isolated': '# Phase 2 — Apply ACP store migration only' in RUNBOOK,
    'live boundary migration isolated': '# Phase 3 — Apply narrow live-boundary migration only' in RUNBOOK,
    'edge deploy separate checkpoint': '# Phase 4 — Edge Function deployment checkpoint' in RUNBOOK,
    'root grant separate checkpoint': '# Phase 5 — Root/parent grant bootstrap checkpoint' in RUNBOOK,
    'admin workflow separate checkpoint': '# Phase 6 — Dedicated admin workflow checkpoint' in RUNBOOK,
    'staging e2e canary exists': '# Phase 7 — Staging-scope end-to-end canary' in RUNBOOK,
    'emergency containment exists': '# Emergency containment' in RUNBOOK,
    'audit preservation is mandatory': 'do not drop the audit store' in RUNBOOK.lower(),
    'service role direct DML prohibited': 'service_role' in RUNBOOK and 'must never receive direct INSERT/UPDATE/DELETE/TRUNCATE rights' in RUNBOOK,
    'runtime root grant prohibited': 'Runtime root-grant issuance is intentionally impossible' in RUNBOOK,
    'production capabilities excluded': '`production.approve`' in RUNBOOK and '`production.promote`' in RUNBOOK,
    'production target not broadened': 'do not broaden to production target environment' in RUNBOOK,
    'exact replay canary required': 'Exact replay returns the same grant ID' in RUNBOOK,
    'changed replay fail closed required': 'changed-input replay with same action ID' in RUNBOOK,
    'cross operation replay blocked': 'same action ID reused for another operation' in RUNBOOK,
    'negative OIDC cases required': 'wrong audience' in RUNBOOK and 'wrong workflow/ref/repository' in RUNBOOK,
    'no HTTP-only PASS': 'Do not infer PASS from HTTP status alone.' in RUNBOOK,
    'human production approval preserved': 'Production release approval/promotion remains outside ACP autonomous authority.' in RUNBOOK,
    'completion does not overclaim live': 'never as production-live' in RUNBOOK,
}

# Rollout documentation must not silently authorize production mutation.
for forbidden in (
    'Status: APPROVED',
    'production_applied: true',
    'edge_deployed: true',
    'AUTO-APPROVE',
    'AUTO-PROMOTE',
):
    checks[f'forbidden authorization marker absent: {forbidden}'] = forbidden not in RUNBOOK

failed = [name for name, ok in checks.items() if not ok]
result = {
    'schema_version': '1.0',
    'suite': 'agent-control-plane-production-rollout-runbook',
    'status': 'PASS' if not failed else 'FAIL',
    'production_applied': False,
    'edge_deployed': False,
    'checks': checks,
}
print(json.dumps(result, indent=2, sort_keys=True))
if failed:
    for name in failed:
        print(f'FAIL: {name}', file=sys.stderr)
    raise SystemExit(1)
