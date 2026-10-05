from pathlib import Path
import json,re,sys

root=Path(__file__).resolve().parents[2]
wf=(root/'.github/workflows/vl-operational-proof-harness.yml').read_text()
probe=(root/'vl/ops/realtime_e2e_probe.mjs').read_text()
trigger=json.loads((root/'vl/ops/realtime_e2e_trigger.json').read_text())
doc=(root/'vl/ops/OPERATIONAL_PROOF_CLOSURE_2026-10-05.md').read_text()

required=[
 'REALTIME_E2E_PASS','realtime_e2e_probe','postgres_changes',
 'Issue #483','USD 0.01344/hour','digest equality',
 'Production remains HOLD'
]
blob='\n'.join([wf,probe,doc])
missing=[x for x in required if x not in blob]
if missing:
    raise SystemExit('missing operational proof contract tokens: '+repr(missing))

if trigger.get('enabled') is not False or trigger.get('nonce') is not None:
    raise SystemExit('realtime trigger must default fail-closed')

for forbidden in [
 'production.approve','production_release_authorized=true',
 'set status=\'active\'','automatic restore authorized'
]:
    if forbidden.lower() in blob.lower():
        raise SystemExit('forbidden authority token: '+forbidden)

if not re.search(r'alter publication supabase_realtime drop table public\.realtime_e2e_probe',doc,re.I):
    raise SystemExit('missing Realtime cleanup contract')
normalized_doc=doc.lower().replace('**','')
if 'does not claim provider pitr or physical-backup recovery' not in normalized_doc:
    raise SystemExit('restore drill scope must not be overstated')

print('VL_OPERATIONAL_PROOF_HARNESS=PASS')
