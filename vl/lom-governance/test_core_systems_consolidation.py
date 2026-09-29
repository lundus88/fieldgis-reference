import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = subprocess.run(
    [sys.executable, str(ROOT / "vl/lom-governance/validate_core_systems_consolidation.py")],
    capture_output=True,
    text=True,
)
assert p.returncode == 0, p.stdout + p.stderr
assert "LOM_CORE_SYSTEMS_CONSOLIDATION=PASS" in p.stdout
