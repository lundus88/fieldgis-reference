import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).parent
subprocess.run(['python3', str(ROOT/'assess_portfolio.py')], check=True)
portfolio=json.loads((ROOT/'portfolio-snapshot.json').read_text())
exceptions=json.loads((ROOT/'director-exceptions.json').read_text())
executive=json.loads((ROOT/'executive-snapshot.json').read_text())

by_id={x['project_id']:x for x in portfolio['portfolio']}
assert by_id['kontenstudio']['health']=='HOLD'
assert by_id['lunduslead']['health']=='BLOCKED'
assert by_id['ebkl']['health']=='REVIEW'
assert by_id['sabahlot']['health']=='REVIEW'
assert portfolio['production_authority']=='HUMAN_ONLY'
assert executive['production_authority']=='HUMAN_ONLY'
assert executive['director_queue']['open_count']==len(exceptions['exceptions'])
for item in portfolio['portfolio']:
    assert item['evidence_refs'], item
print('LOM P3 RUNTIME TESTS: PASS')
