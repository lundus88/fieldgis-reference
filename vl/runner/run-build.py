#!/usr/bin/env python3
"""Trusted harness for the credential-free VL generated-code build job."""
from __future__ import annotations
import hashlib, json, os, pathlib, re, shutil, subprocess, sys, tarfile

ROOT=pathlib.Path.cwd().resolve()
CONTRACT=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
BUILDER=CONTRACT["builder_key"]
ARTS=CONTRACT["generated_artifacts"]
SANDBOX=(ROOT/"vl-harness/sandbox-exec.sh").resolve()
WORK=(ROOT/"workspace").resolve()
MAX_OUTPUT=2_147_483_648

def run(args, cwd=ROOT, *, sandbox=False):
    command=[str(SANDBOX),str(cwd),*args] if sandbox else args
    subprocess.run(command,cwd=cwd,check=True,env={
        "PATH":os.environ["PATH"],"HOME":os.environ.get("HOME",""),
        "GITHUB_WORKSPACE":os.environ["GITHUB_WORKSPACE"],
        "VL_SANDBOX_CPU_SECONDS":"900","VL_SANDBOX_MEMORY_BYTES":"6442450944",
        "VL_SANDBOX_FILE_BYTES":str(MAX_OUTPUT),"VL_SANDBOX_PROCESSES":"128",
        "VL_SANDBOX_WALL_SECONDS":"1200","VL_SANDBOX_DISK_BYTES":"4294967296",
    })

def safe_write(root:pathlib.Path, rel:str, content:str):
    pure=pathlib.PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts or any(p in ("",".","~") for p in pure.parts):
        raise ValueError("unsafe artifact path")
    target=root.joinpath(*pure.parts)
    cursor=root
    for part in pure.parts[:-1]:
        cursor=cursor/part
        if cursor.exists() and cursor.is_symlink(): raise ValueError("symlink parent forbidden")
        cursor.mkdir(exist_ok=True)
    if target.exists() and target.is_symlink(): raise ValueError("symlink target forbidden")
    target.write_text(content,encoding="utf-8")

def normalized(text, suffix):
    if suffix.endswith((".dart",".ts",".tsx",".js",".jsx")):
        return re.sub(r"\\n(?=(?:import|export|class|function|const|let|var|void|String|Future|Widget|interface|type|Deno)\\b)","\n",text)
    return text

def generated(prefixes):
    for item in ARTS:
        path=item["path"]
        prefix=next((p for p in prefixes if path.startswith(p)),None)
        if prefix: yield path[len(prefix):],item["content"]

def archive(source:pathlib.Path, output:pathlib.Path, members):
    with tarfile.open(output,"w:gz",dereference=False) as tf:
        for member in members:
            p=source/member
            if p.is_symlink(): raise ValueError("artifact symlink forbidden")
            tf.add(p,arcname=member,recursive=True)

shutil.rmtree(WORK,ignore_errors=True)
WORK.mkdir()
artifact=None

if BUILDER=="mobile-flutter-v1":
    root=WORK/"mobile"
    # Trusted template and dependencies are prepared before generated source exists.
    run(["flutter","create",str(root),"--platforms=android","--org","com.vrslabs","--project-name","vl_generated_app"])
    (root/"test/widget_test.dart").unlink(missing_ok=True)
    run(["flutter","pub","get"],root)
    for rel,text in generated(("mobile/flutter/","mobile/")): safe_write(root,rel,normalized(text,rel))
    main=root/"lib/main.dart"
    if not main.exists(): safe_write(root,"lib/main.dart","import 'package:flutter/material.dart';\nvoid main()=>runApp(const MaterialApp(home:Scaffold(body:Text('VL Generated App'))));\n")
    run(["flutter","analyze","--no-fatal-infos"],root,sandbox=True)
    run(["flutter","build","apk","--debug","--offline"],root,sandbox=True)
    artifact=root/"build/app/outputs/flutter-apk/app-debug.apk"

elif BUILDER in {"gis-web-v1","web-react-v1","pwa-react-v1"}:
    gis=BUILDER=="gis-web-v1"; root=WORK/("gis" if gis else "web"); (root/"src").mkdir(parents=True)
    package={"name":"vl-generated","private":True,"version":"0.0.0","type":"module","scripts":{"build":"vite build"}}
    if gis: package|={"dependencies":{"maplibre-gl":"6.6.0"},"devDependencies":{"typescript":"5.8.3","vite":"8.2.2"}}
    else: package|={"dependencies":{"react":"19.2.8","react-dom":"19.2.8"},"devDependencies":{"vite":"8.2.2"}}
    safe_write(root,"package.json",json.dumps(package,separators=(",",":")))
    if gis:
        safe_write(root,"index.html",'<!doctype html><div id="map"></div><script type="module" src="/src/main.ts"></script>')
        safe_write(root,"src/main.ts","import * as maplibregl from 'maplibre-gl'; import 'maplibre-gl/dist/maplibre-gl.css'; const map=new maplibregl.Map({container:'map',style:'https://demotiles.maplibre.org/style.json'}); (globalThis as any).__VL_MAPLIBRE_RUNTIME__={booted:true};")
        items=generated(("gis/",))
    else:
        (root/"public").mkdir()
        safe_write(root,"index.html",'<!doctype html><div id="root"></div><script type="module" src="/src/main.tsx"></script>')
        items=generated(("web/",))
    for rel,text in items:
        if rel in {"package.json","package-lock.json","npm-shrinkwrap.json","yarn.lock","pnpm-lock.yaml"}: raise ValueError("generated dependency manifest forbidden")
        safe_write(root,rel,normalized(text,rel))
    if not gis:
        if not (root/"src/App.tsx").exists(): safe_write(root,"src/App.tsx","import React from 'react'; export default function App(){return <main>VL Generated Web</main>}")
        if not (root/"src/main.tsx").exists(): safe_write(root,"src/main.tsx","import React from 'react'; import{createRoot}from'react-dom/client'; import App from './App'; createRoot(document.getElementById('root')!).render(<App/>);")
        if BUILDER=="pwa-react-v1":
            safe_write(root,"public/manifest.webmanifest",'{"name":"VL PWA","short_name":"VL","start_url":"/","display":"standalone"}')
            safe_write(root,"public/sw.js","self.addEventListener('install',()=>self.skipWaiting());")
    # Only fixed, trusted manifests reach the explicit registry; lifecycle scripts are disabled.
    run(["npm","install","--ignore-scripts","--no-audit","--no-fund","--registry=https://registry.npmjs.org"],root)
    run(["npm","run","build"],root,sandbox=True)
    out=root/".vercel/output"; (out/"static").mkdir(parents=True)
    shutil.copytree(root/"dist",out/"static",dirs_exist_ok=True,symlinks=False)
    safe_write(out,"config.json",'{"version":3}')
    if BUILDER=="pwa-react-v1" and not (out/"static/manifest.webmanifest").is_file(): raise ValueError("PWA manifest missing")
    artifact=WORK/("vl-gis-build.tgz" if gis else "vl-web-build.tgz")
    archive(root,artifact,[".vercel/output","package.json","package-lock.json"])

elif BUILDER=="api-service-v1":
    root=WORK/"api"; root.mkdir()
    for rel,text in generated(("api/",)): safe_write(root,rel,normalized(text,rel))
    if not (root/"index.ts").exists(): safe_write(root,"index.ts","Deno.serve(()=>new Response(JSON.stringify({ok:true})));")
    run(["deno","check","--cached-only","index.ts"],root,sandbox=True)
    artifact=WORK/"vl-api-build.tgz"; archive(root,artifact,[p.name for p in root.iterdir()])
else:
    raise ValueError("unsupported builder")

if not artifact or not artifact.is_file() or artifact.stat().st_size>MAX_OUTPUT: raise ValueError("invalid build artifact")
digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
result={"success":True,"factory_run_id":CONTRACT["factory_run_id"],"builder_key":BUILDER,"artifact_sha256":digest,"artifact_path":str(artifact.relative_to(ROOT)).replace("\\\\","/"),"build_boundary":"network-none-cgroup-mount-pid-namespace","contract_schema":1}
pathlib.Path("build-result.json").write_text(json.dumps(result,separators=(",",":"),sort_keys=True))
