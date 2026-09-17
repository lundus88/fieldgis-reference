from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

PRIMARY_CRON = '37 0 * * *'
CATCHUP_CRON = '47 6 * * *'
PRIMARY_GRACE_MINUTES = 120
WORKFLOW_FILE = 'lom-p4-director-loop.yml'
OUT = Path(__file__).resolve().parent
GUARD_EVIDENCE = OUT / 'scheduler-guard-evidence.json'


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def evaluate_schedule(
    *,
    event_name: str,
    schedule_expr: str,
    now: datetime,
    prior_evidence_runs: Iterable[dict],
    discovery_error: str | None = None,
) -> dict:
    prior = list(prior_evidence_runs)
    base = {
        'schema': 'lom.director-scheduler-guard/1',
        'evaluated_at': _iso(now),
        'event_name': event_name,
        'schedule': schedule_expr,
        'prior_successful_evidence_runs': prior,
        'execution_authority': 'NONE',
        'production_authority': 'HUMAN_ONLY',
        'cross_repo_write': 'DISABLED',
    }

    if event_name != 'schedule':
        return {
            **base,
            'action': 'RUN',
            'scheduler_status': 'NOT_SCHEDULED',
            'observed_condition': 'NON_SCHEDULE_EVENT',
            'reason': 'CI_OR_MANUAL_VALIDATION',
        }

    if discovery_error:
        return {
            **base,
            'action': 'RUN',
            'scheduler_status': 'SCHEDULER_DEGRADED',
            'observed_condition': 'GUARD_DISCOVERY_UNAVAILABLE',
            'reason': discovery_error,
        }

    if prior:
        return {
            **base,
            'action': 'SKIP',
            'scheduler_status': 'SCHEDULER_OK',
            'observed_condition': 'DAILY_BRIEF_ALREADY_PRODUCED',
            'reason': 'SUCCESSFUL_DIRECTOR_BRIEF_ARTIFACT_EXISTS_TODAY',
        }

    if schedule_expr == PRIMARY_CRON:
        scheduled = now.astimezone(timezone.utc).replace(hour=0, minute=37, second=0, microsecond=0)
        delay_minutes = max(0, int((now.astimezone(timezone.utc) - scheduled).total_seconds() // 60))
        status = 'SCHEDULER_OK' if delay_minutes <= PRIMARY_GRACE_MINUTES else 'DELAYED'
        return {
            **base,
            'action': 'RUN',
            'scheduler_status': status,
            'observed_condition': 'PRIMARY_TRIGGER',
            'reason': 'PRIMARY_WITHIN_GRACE' if status == 'SCHEDULER_OK' else 'PRIMARY_TRIGGER_DELAYED',
            'delay_minutes': delay_minutes,
        }

    if schedule_expr == CATCHUP_CRON:
        return {
            **base,
            'action': 'RUN',
            'scheduler_status': 'RECOVERED',
            'observed_condition': 'MISSED_PRIMARY',
            'reason': 'NO_SUCCESSFUL_DIRECTOR_BRIEF_ARTIFACT_TODAY',
        }

    return {
        **base,
        'action': 'HOLD',
        'scheduler_status': 'SCHEDULER_DEGRADED',
        'observed_condition': 'UNKNOWN_SCHEDULE',
        'reason': 'UNREGISTERED_SCHEDULE_EXPRESSION',
    }


def _github_json(url: str, token: str) -> dict:
    req = Request(
        url,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'lom-director-scheduler-guard',
        },
    )
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def discover_today_successful_evidence_runs(
    *, repository: str, token: str, current_run_id: str, now: datetime
) -> list[dict]:
    if not repository or not token:
        raise RuntimeError('MISSING_GITHUB_REPOSITORY_OR_TOKEN')

    runs_url = (
        f'https://api.github.com/repos/{repository}/actions/workflows/{WORKFLOW_FILE}/runs'
        '?event=schedule&status=completed&per_page=30'
    )
    payload = _github_json(runs_url, token)
    day_start = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    found: list[dict] = []

    for run in payload.get('workflow_runs', []):
        if str(run.get('id')) == str(current_run_id):
            continue
        if run.get('conclusion') != 'success' or run.get('head_branch') != 'main':
            continue
        created_at = run.get('created_at')
        if not created_at:
            continue
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        if created < day_start:
            continue

        run_id = run['id']
        artifacts = _github_json(
            f'https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100', token
        )
        expected = f'lom-director-brief-{run_id}'
        if any(
            item.get('name') == expected and not item.get('expired', False)
            for item in artifacts.get('artifacts', [])
        ):
            found.append({'run_id': str(run_id), 'created_at': created_at, 'artifact': expected})

    return found


def _write_outputs(decision: dict) -> None:
    output_path = os.environ.get('GITHUB_OUTPUT')
    if not output_path:
        return
    with open(output_path, 'a', encoding='utf-8') as handle:
        for key in ('action', 'scheduler_status', 'observed_condition', 'reason'):
            handle.write(f'{key}={decision[key]}\n')


def main() -> int:
    now = datetime.now(timezone.utc)
    event_name = os.environ.get('GITHUB_EVENT_NAME', '')
    schedule_expr = os.environ.get('GITHUB_EVENT_SCHEDULE', '')
    prior: list[dict] = []
    discovery_error = None

    if event_name == 'schedule':
        try:
            prior = discover_today_successful_evidence_runs(
                repository=os.environ.get('GITHUB_REPOSITORY', ''),
                token=os.environ.get('GITHUB_TOKEN', ''),
                current_run_id=os.environ.get('GITHUB_RUN_ID', ''),
                now=now,
            )
        except Exception as exc:  # fail-safe read-only recovery run rather than miss the brief
            discovery_error = f'{type(exc).__name__}:{exc}'

    decision = evaluate_schedule(
        event_name=event_name,
        schedule_expr=schedule_expr,
        now=now,
        prior_evidence_runs=prior,
        discovery_error=discovery_error,
    )
    decision['github_run_id'] = os.environ.get('GITHUB_RUN_ID', 'local')
    decision['github_sha'] = os.environ.get('GITHUB_SHA', '')
    GUARD_EVIDENCE.write_text(json.dumps(decision, indent=2) + '\n', encoding='utf-8')
    _write_outputs(decision)
    print(json.dumps(decision, sort_keys=True))
    return 2 if decision['action'] == 'HOLD' else 0


if __name__ == '__main__':
    raise SystemExit(main())
