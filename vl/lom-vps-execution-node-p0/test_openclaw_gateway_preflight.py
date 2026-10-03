from pathlib import Path

ROOT = Path(__file__).resolve().parent
script = (ROOT / "openclaw_gateway_preflight.sh").read_text(encoding="utf-8")
runbook = (ROOT / "OPENCLAW_GATEWAY_UPGRADE_PREFLIGHT.md").read_text(encoding="utf-8")

required = [
    "openclaw --version",
    "openclaw update status --json",
    "openclaw update --dry-run --json",
    "openclaw health",
    "openclaw gateway status --deep --json",
    "openclaw doctor --lint --json",
]
for item in required:
    assert item in script, item

for forbidden in [
    "openclaw update\n",
    "gateway restart",
    "systemctl restart",
    "sudo ",
    "docker ",
    "npm i -g",
]:
    assert forbidden not in script, forbidden

assert "umask 077" in script
assert "chmod 700" in script
assert "chmod 600" in script
assert "No update, restart" in runbook
assert "verified pre-update backup" in runbook
assert "PR #181" in runbook

print("OpenClaw Gateway preflight regression PASS")
