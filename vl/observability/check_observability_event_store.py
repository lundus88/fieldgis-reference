from pathlib import Path

SQL = (Path(__file__).resolve().parent / 'observability-event-store.sql').read_text().lower()

required = [
    'create table if not exists public.vl_observability_events',
    'enable row level security',
    'no update/delete policies are defined',
    'event_sha256 text not null unique',
    'source_decision_sha256 text not null',
    'release_candidate_blocked_observed',
    'historical_orphan_candidate_observed',
    'current_path_regression_observed',
    'vl_observability_no_secret_payload',
    'grants no production approval or factory-run state mutation authority',
]

missing = [item for item in required if item not in SQL]
if missing:
    raise SystemExit('OBSERVABILITY EVENT STORE CONTRACT: FAIL missing ' + ', '.join(missing))

for forbidden in ('update public.factory_runs', 'delete from public.factory_runs', 'production.approve', 'service_role'):
    if forbidden in SQL:
        raise SystemExit(f'OBSERVABILITY EVENT STORE CONTRACT: FAIL forbidden marker {forbidden}')

print('OBSERVABILITY EVENT STORE CONTRACT: PASS')
