#!/usr/bin/env bash
set -euo pipefail

fail=0

# 1. Sensitive GitHub/OIDC/control-plane variables must not be present.
for name in ACTIONS_ID_TOKEN_REQUEST_TOKEN ACTIONS_ID_TOKEN_REQUEST_URL VRS_OIDC_TOKEN SUPABASE_SERVICE_ROLE_KEY GITHUB_TOKEN; do
  if printenv "$name" >/dev/null 2>&1; then
    echo "FAIL: sensitive environment variable visible: $name" >&2
    fail=1
  fi
done

# 2. Docker socket must not be available.
if [ -S /var/run/docker.sock ]; then
  echo "FAIL: docker socket exposed" >&2
  fail=1
fi

# 3. Attempt writes outside the workspace; read-only root should block them.
if touch /vl-sandbox-escape-test 2>/dev/null; then
  echo "FAIL: root filesystem writable" >&2
  rm -f /vl-sandbox-escape-test || true
  fail=1
fi

# 4. Confirm workspace remains writable for legitimate build output.
printf 'sandbox-ok\n' > /workspace/.vl-sandbox-write-test

# 5. Network must fail closed. Either command may be absent; if curl exists and can reach
# a public endpoint the sandbox is not isolated.
if command -v curl >/dev/null 2>&1; then
  if curl -fsS --connect-timeout 2 https://example.com >/dev/null 2>&1; then
    echo "FAIL: network egress available" >&2
    fail=1
  fi
fi

# 6. Metadata/control-plane style addresses must not be reachable.
if command -v curl >/dev/null 2>&1; then
  if curl -fsS --connect-timeout 1 http://169.254.169.254 >/dev/null 2>&1; then
    echo "FAIL: metadata endpoint reachable" >&2
    fail=1
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo "VL GENERATED-CODE SANDBOX PROBE: FAIL" >&2
  exit 1
fi

echo "VL GENERATED-CODE SANDBOX PROBE: PASS"
