#!/usr/bin/env python3
import json, pathlib, re, sys

MAX_FILES=256
MAX_FILE_BYTES=1_000_000
MAX_TOTAL_BYTES=8_000_000
BUILDERS={'mobile-flutter-v1','gis-web-v1','web-react-v1','pwa-react-v1','api-service-v1'}
PREFIX={'mobile-flutter-v1':('mobile/','mobile/flutter/'),'gis-web-v1':('gis/',),'web-react-v1':('web/',),'pwa-react-v1':('web/',),'api-service-v1':('api/',)}
FORBIDDEN_NAMES={'package.json','package-lock.json','npm-shrinkwrap.json','yarn.lock','pnpm-lock.yaml','pubspec.yaml','pubspec.lock','build.rs'}

src=pathlib.Path(sys.argv[1]); dst=pathlib.Path(sys.argv[2])
d=json.loads(src.read_text(encoding='utf-8'))
if set(d)-{'schema_version','factory_run_id','builder_key','app_spec','generated_artifacts'}: raise SystemExit('unexpected contract field')
if d.get('schema_version')!=1 or d.get('builder_key') not in BUILDERS: raise SystemExit('invalid contract identity')
if not re.fullmatch(r'[0-9a-f-]{36}',str(d.get('factory_run_id',''))): raise SystemExit('invalid run id')
arts=d.get('generated_artifacts')
if not isinstance(arts,list) or len(arts)>MAX_FILES: raise SystemExit('invalid artifact count')
total=0
for a in arts:
    if not isinstance(a,dict) or set(a)-{'path','content'}: raise SystemExit('invalid artifact object')
    p=a.get('path'); c=a.get('content')
    if not isinstance(p,str) or not isinstance(c,str) or '\\' in p or '\x00' in p: raise SystemExit('invalid artifact types')
    pure=pathlib.PurePosixPath(p)
    if pure.is_absolute() or '..' in pure.parts or any(part in ('','.','~') for part in pure.parts): raise SystemExit('unsafe artifact path')
    if not p.startswith(PREFIX[d['builder_key']]): raise SystemExit('artifact prefix mismatch')
    if pure.name in FORBIDDEN_NAMES: raise SystemExit('generated dependency/build manifest forbidden')
    n=len(c.encode('utf-8')); total+=n
    if n>MAX_FILE_BYTES or total>MAX_TOTAL_BYTES: raise SystemExit('artifact size limit exceeded')
dst.write_text(json.dumps(d,separators=(',',':'),sort_keys=True),encoding='utf-8')
