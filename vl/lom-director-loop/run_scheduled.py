import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
refresh = runpy.run_path(str(ROOT / 'lom-5-operational-maturity' / 'scheduled_evidence_refresh.py'))
refresh['main']()
director = runpy.run_path(str(Path(__file__).with_name('director_loop.py')))
brief = director['build']()
print(f"LOM SCHEDULED DIRECTOR LOOP: PASS ({brief['freshness_status']})")
