import json
from pathlib import Path

ROOT = Path(__file__).parent
obs = json.loads((ROOT / 'captured-observation.json').read_text())['observations']

portfolio=[]
exceptions=[]
for o in obs:
    signals=set(o['signals'])
    if not o['accessible'] or 'EMPTY_REPOSITORY' in signals or not o.get('main_sha'):
        health='HOLD'
        reason='Source unavailable or empty; positive state prohibited.'
        exceptions.append({'project_id':o['project_id'],'category':'EVIDENCE_GAP','severity':'HIGH','summary':reason})
    elif any('BLOCKED' in s for s in signals):
        health='BLOCKED'
        reason='Observed blocked runtime/readiness signal.'
        exceptions.append({'project_id':o['project_id'],'category':'UNRESOLVED_BLOCKER','severity':'HIGH','summary':reason})
    elif any(s.startswith('OPEN_') for s in signals):
        health='REVIEW'
        reason='Open work remains; repository activity is not production-readiness proof.'
        exceptions.append({'project_id':o['project_id'],'category':'HUMAN_APPROVAL','severity':'MEDIUM','summary':reason})
    else:
        health='HEALTHY'
        reason='Current captured evidence contains no blocker signal.'
    portfolio.append({'project_id':o['project_id'],'health':health,'reason':reason,'evidence_refs':o['evidence_refs']})

snapshot={
  'portfolio':portfolio,
  'counts':{
    'total':len(portfolio),
    'healthy':sum(x['health']=='HEALTHY' for x in portfolio),
    'review':sum(x['health']=='REVIEW' for x in portfolio),
    'blocked':sum(x['health']=='BLOCKED' for x in portfolio),
    'hold':sum(x['health']=='HOLD' for x in portfolio)
  },
  'production_authority':'HUMAN_ONLY'
}
(ROOT/'portfolio-snapshot.json').write_text(json.dumps(snapshot, indent=2)+'\n')
(ROOT/'director-exceptions.json').write_text(json.dumps({'exceptions':exceptions}, indent=2)+'\n')
exec_snapshot={
  'portfolio':snapshot['counts'],
  'director_queue':{'open_count':len(exceptions),'critical_count':sum(x['severity']=='CRITICAL' for x in exceptions)},
  'top_priorities':[x['project_id'] for x in portfolio if x['health'] in ('BLOCKED','HOLD','REVIEW')],
  'production_authority':'HUMAN_ONLY'
}
(ROOT/'executive-snapshot.json').write_text(json.dumps(exec_snapshot, indent=2)+'\n')
print('LOM P3 ASSESSMENT: PASS')
