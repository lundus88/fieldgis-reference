#!/usr/bin/env python3
import json, sys
from pathlib import Path

ALLOWED_REPO = 'lundus88/ebkl'
FORBIDDEN = {
    'merge_main','force_push','delete_branch','deploy_production','mutate_production',
    'alter_regulatory_tolerance_without_verified_source','alter_numerical_formula_without_evidence',
    'auto_resolve_boundary_conflict','mark_blocked_golden_regression_as_pass'
}
REQUIRED_ALLOWED = {
    'read_repository','read_branch','inspect_tests','prepare_change_plan','prepare_patch',
    'run_non_production_tests','run_syntax_checks','report_golden_regression_status',
    'prepare_pull_request_metadata'
}

def fail(msg):
    print(f'VL e-BKL BUILDER ADAPTER: FAIL - {msg}')
    raise SystemExit(1)

path = Path(sys.argv[1] if len(sys.argv) > 1 else 'vl/projects/ebkl/builder-adapter.json')
doc = json.loads(path.read_text())

if doc.get('schema') != 'vl.ebkl-builder-adapter/1':
    fail('unexpected schema')
if doc.get('project_class') != 'CRITICAL_NUMERICAL / CADASTRAL':
    fail('critical project class missing')
if doc.get('target_repository') != ALLOWED_REPO:
    fail('target repository is not pinned to lundus88/ebkl')
if doc.get('authoritative_development_branch') in (None, '', 'main'):
    fail('development branch must be explicit and non-main')

allowed = set(doc.get('allowed_actions') or [])
if not REQUIRED_ALLOWED.issubset(allowed):
    fail('required safe builder actions missing')
if allowed & FORBIDDEN:
    fail('forbidden action appears in allowed_actions')

forbidden = set(doc.get('forbidden_actions') or [])
if not FORBIDDEN.issubset(forbidden):
    fail('hard forbidden action set incomplete')

pre = doc.get('required_preflight') or {}
if pre.get('repository_must_equal') != ALLOWED_REPO:
    fail('repository preflight pin missing')
if pre.get('branch_must_not_equal') != 'main':
    fail('main branch prohibition missing')
if pre.get('production_locked') is not True:
    fail('production lock must be true')
if pre.get('crs_datum_explicit') is not True:
    fail('CRS/datum explicit requirement missing')
if pre.get('boundary_conflict_state') != 'HUMAN_REVIEW_REQUIRED':
    fail('boundary conflict human-review lock missing')
if pre.get('golden_regression_must_be_reported') is not True:
    fail('Golden Regression reporting lock missing')
if pre.get('verified_regulatory_source_required') is not True:
    fail('verified regulatory source lock missing')

cmds = doc.get('validation_commands') or []
for required in ('npm test','node --check app.mjs'):
    if required not in cmds:
        fail(f'missing validation command: {required}')

handoff = doc.get('handoff') or {}
if handoff.get('maximum_authority') != 'PR_PREPARATION_ONLY':
    fail('builder authority exceeds PR preparation')
if handoff.get('merge_authority') != 'HUMAN_ONLY':
    fail('merge authority must remain human-only')
if handoff.get('production_authority') != 'HUMAN_ONLY':
    fail('production authority must remain human-only')

print('VL e-BKL BUILDER ADAPTER: PASS')
