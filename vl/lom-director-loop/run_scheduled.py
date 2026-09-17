from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_OBSERVATION = ROOT / 'lom-portfolio-runtime' / 'captured-observation.json'
OUT = Path(__file__).resolve().parent
RUN_EVIDENCE = OUT / 'scheduled-run-evidence.json'


def sha256_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_run_manifest(
    brief: dict,
    source_digest: str,
    run_id: str,
    github_sha: str,
    scheduler: dict | None = None,
) -> dict:
    scheduler = scheduler or {}
    return {
        'schema': 'lom.director-brief-run/2',
        'generated_at': brief['generated_at'],
        'github_run_id': run_id,
        'github_sha': github_sha,
        'scheduler': {
            'event_name': scheduler.get('event_name', ''),
            'schedule': scheduler.get('schedule', ''),
            'status': scheduler.get('status', 'UNKNOWN'),
            'guard_action': scheduler.get('guard_action', 'UNKNOWN'),
            'observed_condition': scheduler.get('observed_condition', ''),
            'reason': scheduler.get('reason', ''),
        },
        'source_snapshot': {
            'path': 'vl/lom-portfolio-runtime/captured-observation.json',
            'sha256': source_digest,
            'captured_at': brief['source_captured_at'],
            'freshness_status': brief['freshness_status'],
            'source_age_hours': brief['source_age_hours'],
        },
        'outputs': [
            'vl/lom-director-loop/daily-executive-brief.json',
            'vl/lom-director-loop/DAILY_DIRECTOR_BRIEF.md',
            'vl/lom-director-loop/scheduler-guard-evidence.json',
        ],
        'execution_authority': 'NONE',
        'execution_performed': False,
        'production_authority': 'HUMAN_ONLY',
        'protected_main_merge': 'HUMAN_ONLY',
    }


def main() -> int:
    before = sha256_file(CANONICAL_OBSERVATION)

    director = runpy.run_path(str(OUT / 'director_loop.py'))
    brief = director['build']()

    after = sha256_file(CANONICAL_OBSERVATION)
    if before != after:
        raise RuntimeError('CANONICAL_PORTFOLIO_OBSERVATION_MUTATED')

    scheduler = {
        'event_name': os.environ.get('GITHUB_EVENT_NAME', ''),
        'schedule': os.environ.get('GITHUB_EVENT_SCHEDULE', ''),
        'status': os.environ.get('LOM_SCHEDULER_STATUS', 'UNKNOWN'),
        'guard_action': os.environ.get('LOM_SCHEDULER_ACTION', 'UNKNOWN'),
        'observed_condition': os.environ.get('LOM_SCHEDULER_CONDITION', ''),
        'reason': os.environ.get('LOM_SCHEDULER_REASON', ''),
    }
    manifest = build_run_manifest(
        brief,
        before,
        os.environ.get('GITHUB_RUN_ID', 'local'),
        os.environ.get('GITHUB_SHA', ''),
        scheduler,
    )
    RUN_EVIDENCE.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(
        f"LOM SCHEDULED DIRECTOR LOOP: PASS ({brief['freshness_status']}; "
        f"scheduler={scheduler['status']}; canonical snapshot preserved)"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
