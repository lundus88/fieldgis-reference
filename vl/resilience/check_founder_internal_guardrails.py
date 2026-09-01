from pathlib import Path
import sys

p=Path('vl/migrations/20260901_founder_internal_usage_guardrails.sql')
text=p.read_text() if p.exists() else ''
errors=[]
def need(label, token):
    if token not in text: errors.append(label)

need('staging-only founder/internal entry missing', "new.target_environment <> 'staging'")
need('production lock enforcement missing', 'new.production_locked is distinct from true')
need('owner/admin founder authority missing', "pm.role in ('owner','admin')")
need('classification requirement missing', 'internal_usage_classification')
need('estimated cost attribution missing', 'estimated_cost_units')
need('daily run limit missing', 'daily_run_limit')
need('concurrent run limit missing', 'concurrent_run_limit')
need('daily cost limit missing', 'daily_estimated_cost_unit_limit')
need('explicit override function missing', 'request_vrs_internal_usage_override')
need('AAL2 override missing', 'AAL2 MFA required for internal usage override')
need('override reason minimum missing', "length(btrim(reason)) >= 12")
need('override expiry bound missing', "interval '4 hours'")
need('override revocation state missing', 'revoked_at')
need('usage ledger missing', 'private.internal_usage_ledger')
need('audit log missing', 'private.internal_usage_audit')
need('customer quota preservation missing', "customer account is not launch-ready")
need('production approval bypass evidence must be false', "'production_approval_bypassed',false")
need('production promotion bypass evidence must be false', "'production_promotion_bypassed',false")
if 'production.approve' in text or 'approve_vrs_production_release' in text or 'claim_vrs_production_promotion_job' in text:
    errors.append('founder/internal guardrail migration must not invoke production approval/promotion')
if errors:
    print('VL FOUNDER INTERNAL GUARDRAILS: FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('VL FOUNDER INTERNAL GUARDRAILS: PASS')
