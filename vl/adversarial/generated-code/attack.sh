#!/usr/bin/env bash
set -u
fail=0
for key in ACTIONS_ID_TOKEN_REQUEST_TOKEN ACTIONS_ID_TOKEN_REQUEST_URL GITHUB_TOKEN SUPABASE_SERVICE_ROLE_KEY VERCEL_TOKEN OPENAI_API_KEY VL_ISOLATION_CANARY; do
  [[ -z "${!key:-}" ]] || { echo "credential-visible:$key"; fail=1; }
done
[[ ! -s /etc/shadow ]] || { echo 'host-secret-readable'; fail=1; }
touch ../cross-run-marker 2>/dev/null && { echo 'workspace-escape-writable'; fail=1; }
for url in 'http://169.254.169.254/latest/meta-data/' 'https://wczelfmnqpgzfdszxubl.supabase.co/functions/v1/vrs-runner-oidc' 'https://example.com'; do
  curl --max-time 2 -fsS "$url" >/dev/null 2>&1 && { echo "network-egress-available:$url"; fail=1; }
done
python3 - <<'PY' || fail=1
import subprocess
children=[]
try:
    for _ in range(256):
        try: children.append(subprocess.Popen(['sleep','30']))
        except (OSError,BlockingIOError): break
finally:
    for child in children: child.terminate()
    for child in children:
        try: child.wait(timeout=2)
        except Exception: child.kill()
if len(children)>=200: raise SystemExit(f'process-cap-not-enforced:{len(children)}')
print(f'PASS: process-spawn cap enforced after {len(children)} children')
PY
test "$fail" -eq 0 && echo "PASS: hostile credential, metadata, control-plane, egress, traversal, and process-spawn attempts contained"
exit "$fail"
