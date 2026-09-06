#!/usr/bin/env bash
set -euo pipefail

BUILDER="${1:?builder key required}"
ARTIFACT_PATH="${2:?artifact path required}"
SOURCE_SHA="${3:?source sha required}"
CLAIM_JSON="${4:-claim.json}"

case "$BUILDER" in
  web-react-v1|pwa-react-v1|gis-web-v1) ;;
  *) echo "unsupported preview builder: $BUILDER" >&2; exit 64 ;;
esac

[ -s "$ARTIFACT_PATH" ] || { echo "missing immutable factory artifact: $ARTIFACT_PATH" >&2; exit 65; }
[ -s "$CLAIM_JSON" ] || { echo "missing claim json" >&2; exit 66; }

ARTIFACT_SHA256=$(sha256sum "$ARTIFACT_PATH" | awk '{print $1}')
APP_SPEC_SHA256=$(python3 - "$CLAIM_JSON" <<'PY'
import hashlib,json,sys
claim=json.load(open(sys.argv[1]))
spec=claim.get('app_spec')
if not isinstance(spec,dict) or not spec:
    raise SystemExit('missing app_spec for preview evidence')
canonical=json.dumps(spec,sort_keys=True,separators=(',',':'),ensure_ascii=False)
print(hashlib.sha256(canonical.encode('utf-8')).hexdigest())
PY
)

rm -rf preview-root vl/visual-preview/evidence-factory preview-tools
mkdir -p preview-root vl/visual-preview/evidence-factory preview-tools

tar -xzf "$ARTIFACT_PATH" -C preview-root
STATIC_ROOT="preview-root/.vercel/output/static"
[ -s "$STATIC_ROOT/index.html" ] || { echo "missing .vercel/output/static/index.html" >&2; exit 67; }

python3 - "$BUILDER" > vl/visual-preview/evidence-factory/acceptance-inventory.json <<'PY'
import json,sys
builder=sys.argv[1]
selectors=['#map'] if builder=='gis-web-v1' else ['#root']
print(json.dumps({
  'schema':'vl.visual-preview-acceptance/1',
  'builder_key':builder,
  'required_selectors':selectors,
  'required_text':[]
},indent=2))
PY

python3 -m http.server 4173 --bind 127.0.0.1 --directory "$STATIC_ROOT" > vl/visual-preview/evidence-factory/http-server.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:4173/ >/dev/null; then break; fi
  sleep 1
done
curl -fsS http://127.0.0.1:4173/ >/dev/null

(
  cd preview-tools
  npm init -y >/dev/null 2>&1
  npm install --ignore-scripts --no-audit --no-fund playwright@1.55.0 >/dev/null
  npx playwright install chromium >/dev/null
)

VL_PREVIEW_URL='http://127.0.0.1:4173/' \
VL_PREVIEW_OUT='vl/visual-preview/evidence-factory' \
VL_SOURCE_SHA="$SOURCE_SHA" \
VL_ARTIFACT_SHA256="$ARTIFACT_SHA256" \
VL_APP_SPEC_SHA256="$APP_SPEC_SHA256" \
VL_BUILDER_KEY="$BUILDER" \
VL_ACCEPTANCE_INVENTORY='vl/visual-preview/evidence-factory/acceptance-inventory.json' \
NODE_PATH="$PWD/preview-tools/node_modules" \
node vl/visual-preview/verify-factory-preview.mjs

python3 - "$APP_SPEC_SHA256" "$ARTIFACT_SHA256" <<'PY'
import json,sys
p='vl/visual-preview/evidence-factory/evidence.json'
d=json.load(open(p))
d['app_spec_hash_algorithm']='sha256(canonical-json-sort-keys-compact-utf8-v1)'
d['factory_enforcement']='POST_BUILD_PRE_CALLBACK'
d['production_authority']=False
json.dump(d,open(p,'w'),indent=2)
PY

echo "VL FACTORY POST-BUILD PREVIEW GATE: PASS"
