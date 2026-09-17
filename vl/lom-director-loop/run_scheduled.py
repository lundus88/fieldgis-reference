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


def build_run_manifest(brief: dict, source_digest: str, run_id: str, github_sha: str) -> dict:
    return {
        'schema': 'lom.director-brief-run/1',
        'generated_at': brief['generated_at'],
        'github_run_id': run_id,
        'github_sha': github_sha,
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

    manifest = build_run_manifest(
        brief,
        before,
        os.environ.get('GITHUB_RUN_ID', 'local'),
        os.environ.get('GITHUB_SHA', ''),
    )
    RUN_EVIDENCE.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f"LOM SCHEDULED DIRECTOR LOOP: PASS ({brief['freshness_status']}; canonical snapshot preserved)")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
