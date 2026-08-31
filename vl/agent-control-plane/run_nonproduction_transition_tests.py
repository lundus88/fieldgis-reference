from datetime import datetime, timezone
import sys

from nonproduction_transition import execute_guarded_transition
from runtime_policy import canonical_digest

NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def grant(capabilities=None, revoked_at=None):
    return {
        'grant_id': 'g1',
        'agent_id': 'agent-planner',
        'capabilities': capabilities or ['factory.plan'],
        'scope': {'factory_run_id': 'run-1'},
        'budget': {'timeout_seconds': 30, 'max_retries': 0, 'max_cost_minor': 0},
        'valid_until': '2026-09-02T00:00:00Z',
        'revoked_at': revoked_at,
        'delegated_from_grant_id': None,
    }


def action(capability='factory.plan', actor='agent-planner'):
    payload = {'factory_run_id': 'run-1', 'operation': 'plan'}
    return {
        'action_id': 'act-1',
        'actor_id': actor,
        'capability': capability,
        'scope': {'factory_run_id': 'run-1'},
        'budget': {'timeout_seconds': 10, 'max_retries': 0, 'max_cost_minor': 0},
        'requested_at': '2026-08-31T23:59:00Z',
        'expires_at': '2026-09-01T00:05:00Z',
        'input_digest': canonical_digest(payload),
        'provenance': {'source_type': 'test', 'source_id': 'acp-ci'},
        'input': payload,
    }


def run_case(name, act, grants, expected_applied, expected_reason):
    calls = []
    result = execute_guarded_transition(
        act, grants, 'g1', lambda a: calls.append(a['action_id']) or {'state': 'planned'}, now=NOW
    )
    ok = result.applied is expected_applied and result.decision.get('reason_code') == expected_reason
    ok = ok and ((len(calls) == 1) if expected_applied else (len(calls) == 0))
    print(f"{'PASS' if ok else 'FAIL'}: {name} -> {result.decision.get('reason_code')}")
    return ok


cases = [
    run_case('allowed factory.plan invokes transition exactly once', action(), {'g1': grant()}, True, 'ALLOW_POLICY_MATCH'),
    run_case('ungranted capability never invokes transition', action('factory.enqueue'), {'g1': grant()}, False, 'DENY_CAPABILITY_NOT_GRANTED'),
    run_case('revoked grant fails closed', action(), {'g1': grant(revoked_at='2026-08-31T23:58:00Z')}, False, 'DENY_POLICY_UNAVAILABLE'),
    run_case('identity mismatch fails closed', action(actor='other-agent'), {'g1': grant()}, False, 'DENY_SCOPE_MISMATCH'),
    run_case('production approval never invokes transition', action('production.approve'), {'g1': grant(['production.approve'])}, False, 'REQUIRE_HUMAN_PRODUCTION_APPROVAL'),
    run_case('production promotion never invokes transition', action('production.promote'), {'g1': grant(['production.promote'])}, False, 'REQUIRE_HUMAN_PRODUCTION_APPROVAL'),
]

if not all(cases):
    sys.exit(1)
print('VL ACP NON-PRODUCTION TRANSITION SUITE: PASS')
