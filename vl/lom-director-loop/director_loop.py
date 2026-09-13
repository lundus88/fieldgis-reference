import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'lom-portfolio-runtime'
OUT = Path(__file__).parent
MAX_AGE_HOURS = 36

SEVERITY_SCORE = {'BLOCKED': 100, 'HOLD': 90, 'REVIEW': 60, 'HEALTHY': 10}


def parse_z(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def assess_health(observation):
    signals = set(observation['signals'])
    if not observation['accessible'] or 'EMPTY_REPOSITORY' in signals or not observation.get('main_sha'):
        return 'HOLD', 'Source unavailable or empty; current positive state prohibited.'
    if any('BLOCKED' in s for s in signals):
        return 'BLOCKED', 'Observed unresolved blocker signal.'
    if any(s.startswith('OPEN_') for s in signals):
        return 'REVIEW', 'Open work remains; review is required.'
    return 'HEALTHY', 'No blocker signal in current captured evidence.'


def bounded_action(project_id, health):
    if health == 'BLOCKED':
        return 'Investigate blocker evidence and prepare a remediation proposal; do not execute protected or production actions.'
    if health == 'HOLD':
        return 'Restore trustworthy source evidence and re-run assessment before any promotion.'
    if health == 'REVIEW':
        return 'Review open work and evidence; prepare a decision package for the Director if authority is required.'
    return 'Continue read-only monitoring and evidence refresh.'


def build(now=None):
    now = now or datetime.now(timezone.utc)
    payload = json.loads((RUNTIME / 'captured-observation.json').read_text())
    captured_at = parse_z(payload['captured_at'])
    age_hours = (now - captured_at).total_seconds() / 3600
    stale = age_hours > MAX_AGE_HOURS

    priorities = []
    exceptions = []
    for o in payload['observations']:
        health, reason = assess_health(o)
        if stale:
            health = 'HOLD'
            reason = f'Observation stale ({age_hours:.1f}h > {MAX_AGE_HOURS}h); current-state claim prohibited.'
        item = {
            'project_id': o['project_id'],
            'health': health,
            'priority_score': SEVERITY_SCORE[health],
            'reason': reason,
            'next_action': bounded_action(o['project_id'], health),
            'authority': 'RECOMMENDATION_ONLY',
            'evidence_refs': o['evidence_refs'],
        }
        priorities.append(item)
        if health != 'HEALTHY':
            category = 'EVIDENCE_GAP' if stale or health == 'HOLD' else ('UNRESOLVED_BLOCKER' if health == 'BLOCKED' else 'HUMAN_APPROVAL')
            exceptions.append({
                'project_id': o['project_id'],
                'category': category,
                'severity': 'HIGH' if health in ('BLOCKED', 'HOLD') else 'MEDIUM',
                'decision_required': item['next_action'],
                'evidence_refs': o['evidence_refs'],
            })

    priorities.sort(key=lambda x: (-x['priority_score'], x['project_id']))
    brief = {
        'generated_at': now.isoformat().replace('+00:00', 'Z'),
        'source_captured_at': payload['captured_at'],
        'source_age_hours': round(age_hours, 2),
        'freshness_status': 'STALE' if stale else 'FRESH',
        'production_authority': 'HUMAN_ONLY',
        'protected_main_merge_authority': 'HUMAN_ONLY',
        'financial_commitment_authority': 'HUMAN_ONLY',
        'ranked_priorities': priorities,
        'director_exceptions': exceptions,
    }
    (OUT / 'daily-executive-brief.json').write_text(json.dumps(brief, indent=2) + '\n')
    lines = ['# LOM Daily Director Brief', '', f"Freshness: {brief['freshness_status']} ({brief['source_age_hours']}h)", '', '## Ranked priorities']
    for i, p in enumerate(priorities, 1):
        lines.append(f"{i}. {p['project_id']} — {p['health']} — score {p['priority_score']} — {p['next_action']}")
    lines += ['', f"Director exceptions: {len(exceptions)}", '', 'Production/protected-main/financial authority: HUMAN_ONLY']
    (OUT / 'DAILY_DIRECTOR_BRIEF.md').write_text('\n'.join(lines) + '\n')
    return brief


if __name__ == '__main__':
    result = build()
    print(f"LOM P4 DIRECTOR LOOP: PASS ({result['freshness_status']})")
