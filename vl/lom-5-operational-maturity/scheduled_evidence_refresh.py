from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'lom-portfolio-runtime' / 'source-registry.json'
OUTPUT = ROOT / 'lom-portfolio-runtime' / 'captured-observation.json'


def build_refresh(registry: dict, current_repository: str, current_sha: str, run_id: str, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    sources = registry.get('sources') or []
    observations = []
    for source in sources:
        repo = source.get('repository')
        project_id = source.get('project_id')
        branch = source.get('default_branch') or 'main'
        mode = source.get('mode')

        if mode == 'UNREGISTERED_HOLD':
            observations.append({
                'project_id': project_id,
                'repository': None,
                'accessible': False,
                'default_branch': None,
                'main_sha': None,
                'signals': ['SOURCE_NOT_REGISTERED'],
                'evidence_refs': [
                    f'run:{run_id}',
                    'registry:vl/lom-portfolio-runtime/source-registry.json',
                    f"hold:{source.get('hold_reason') or 'AUTHORITATIVE_SOURCE_NOT_REGISTERED'}",
                ],
            })
            continue

        if mode != 'READ_ONLY':
            raise ValueError('READ_ONLY_OR_UNREGISTERED_HOLD_SOURCE_REQUIRED')

        if repo == current_repository and current_sha:
            observations.append({
                'project_id': project_id,
                'repository': repo,
                'accessible': True,
                'default_branch': branch,
                'main_sha': current_sha,
                'signals': ['MAIN_ACTIVE', 'SCHEDULED_CONTEXT_REFRESH'],
                'evidence_refs': [f'commit:{current_sha}', f'run:{run_id}'],
            })
        else:
            observations.append({
                'project_id': project_id,
                'repository': repo,
                'accessible': False,
                'default_branch': branch,
                'main_sha': None,
                'signals': ['SOURCE_NOT_REFRESHED'],
                'evidence_refs': [f'run:{run_id}', 'status:cross-repo-live-evidence-not-available-in-this-run'],
            })
    return {
        'schema': 'lom.portfolio-observation/2',
        'captured_at': now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'mode': 'READ_ONLY_FAIL_CLOSED',
        'production_authority': 'HUMAN_ONLY',
        'observations': observations,
    }


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding='utf-8'))
    payload = build_refresh(
        registry,
        os.environ.get('GITHUB_REPOSITORY', ''),
        os.environ.get('GITHUB_SHA', ''),
        os.environ.get('GITHUB_RUN_ID', 'local'),
    )
    OUTPUT.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
    fresh = sum(item['accessible'] for item in payload['observations'])
    held = len(payload['observations']) - fresh
    print(f'LOM SCHEDULED EVIDENCE REFRESH: PASS ({fresh} refreshed, {held} fail-closed HOLD)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
