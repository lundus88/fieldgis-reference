#!/usr/bin/env python3
import json,os,re,sys
mode=sys.argv[1]
if mode=='failure':
 d=json.load(open('build-contract.json')); json.dump({'success':False,'factory_run_id':d['factory_run_id'],'builder_key':d['builder_key'],'artifact_sha256':'','artifact_path':'','build_boundary':'network-none-cgroup-mount-pid-namespace','contract_schema':1},open('build-result.json','w'))
elif mode=='outputs':
 r=json.load(open('build-result.json')); allowed={'success','factory_run_id','builder_key','artifact_sha256','artifact_path','build_boundary','contract_schema'}
 if set(r)!=allowed or (r['success'] and not re.fullmatch(r'[0-9a-f]{64}',r['artifact_sha256'])): raise SystemExit('invalid bounded result')
 with open(os.environ['GITHUB_OUTPUT'],'a') as f: f.write(f"ok={str(bool(r['success'])).lower()}\npath={r['artifact_path']}\n")
elif mode=='callback':
 c=json.load(open('control.json')); r=json.load(open('build-result.json')); ok=bool(r['success'])
 if not re.fullmatch(r'[0-9a-f-]{36}',c.get('job_id','')): raise SystemExit('bad job binding')
 if c.get('factory_run_id')!=os.environ['VL_FACTORY_RUN_ID'] or r.get('factory_run_id')!=os.environ['VL_FACTORY_RUN_ID'] or r.get('builder_key')!=os.environ['VL_BUILDER_KEY']: raise SystemExit('cross-run result binding mismatch')
 result={'runner':'github-actions-oidc','builder_key':r['builder_key'],'github_run_id':os.environ['GITHUB_RUN_ID'],'github_sha':os.environ['GITHUB_SHA'],'artifact_name':os.environ['VL_ARTIFACT_NAME'],'artifact_sha256':r['artifact_sha256'],'qa_result':'PASS' if ok else 'FAIL','build_boundary':r['build_boundary']}
 if r['builder_key'] in ('web-react-v1','pwa-react-v1','gis-web-v1'): result.update(artifact_contract='vercel-build-output-v3',immutable_prebuilt=True)
 print(json.dumps({'action':'complete','job_id':c['job_id'],'lease_token':c['lease_token'],'success':ok,'result':result,'error_text':None if ok else 'Isolated build failed'}))
else: raise SystemExit('unknown mode')
