import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "openclaw_gateway_preflight.sh"
script = SCRIPT.read_text(encoding="utf-8")
runbook = (ROOT / "OPENCLAW_GATEWAY_UPGRADE_PREFLIGHT.md").read_text(encoding="utf-8")

required = [
    'OUT="${1:-$HOME/.local/state/lom-openclaw-preflight/$STAMP}"',
    'OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw 2>/dev/null || true)}"',
    '"$OPENCLAW_BIN" --version',
    '"$OPENCLAW_BIN" update status --json',
    '"$OPENCLAW_BIN" update --dry-run --json',
    '"$OPENCLAW_BIN" health',
    '"$OPENCLAW_BIN" gateway status --deep --json',
    '"$OPENCLAW_BIN" doctor --lint --json',
    "RUNTIME_USER_MISMATCH",
]
for item in required:
    assert item in script, item

for forbidden in [
    'OUT="\\${1:-',
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
assert "verified runtime owner is `server`" in runbook
assert "/home/server/.npm-global/bin/openclaw" in runbook
assert "repository checkout ownership is separate from OpenClaw runtime ownership" in runbook

syntax = subprocess.run(
    ["bash", "-n", str(SCRIPT)],
    capture_output=True,
    text=True,
    check=False,
)
assert syntax.returncode == 0, syntax.stderr

with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    bin_dir = tmp_path / "bin"
    home_dir = tmp_path / "home"
    out_dir = tmp_path / "evidence"
    bin_dir.mkdir()
    home_dir.mkdir()

    fake = bin_dir / "openclaw"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "printf 'fake-openclaw %s\\n' \"$*\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["HOME"] = str(home_dir)
    env["OPENCLAW_BIN"] = str(fake)
    env["OPENCLAW_EXPECTED_USER"] = subprocess.check_output(
        ["id", "-un"], text=True
    ).strip()

    result = subprocess.run(
        ["bash", str(SCRIPT), str(out_dir)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(out_dir)
    assert out_dir.is_dir()
    summary = (out_dir / "summary.txt").read_text(encoding="utf-8")
    assert "status=CAPTURED" in summary
    assert f"openclaw_path={fake}" in summary
    for name in [
        "version",
        "update_status",
        "update_dry_run",
        "health",
        "gateway_status",
        "doctor_lint",
    ]:
        assert f"{name}=0" in summary, (name, summary)

print("OpenClaw Gateway preflight regression PASS")
