import json
from pathlib import Path

p = json.loads((Path(__file__).parent / 'continuous-ops-policy.json').read_text())
assert p['mode'] == 'REPORT_ONLY'
assert p['source_access'] == 'READ_ONLY'
assert p['stale_evidence_policy'] == 'HOLD_OR_REVIEW'
assert all(v == 'HUMAN_ONLY' for v in p['authorities'].values())
print('LOM P5 POLICY: PASS')
