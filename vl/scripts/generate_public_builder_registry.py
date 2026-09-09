#!/usr/bin/env python3
"""Generate the intentionally minimal public projection of certification manifests.

The YAML manifests remain the canonical builder registry. This script never emits
evidence IDs, workflow references, private topology, or credentials.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERT = ROOT / "certification"
OUT = ROOT / "public" / "builder-registry.js"

CATALOG = {
    "mobile-flutter-v1": ("Mobile application", "mobile-flutter sandbox", "Android Flutter application artifact", "Android profile only; each production release remains human-approved."),
    "gis-web-v1": ("GIS & mapping", "GIS web sandbox", "Web GIS application", "Certification approval exists; registry activation remains experimental."),
    "web-react-v1": ("Web application", "web/PWA sandbox", "React web application", "Not active until human approval is recorded."),
    "pwa-react-v1": ("Progressive web app", "web/PWA sandbox", "Installable React PWA artifact", "Not active until human approval is recorded."),
    "api-service-v1": ("Backend & API service", "API service sandbox", "Deno API service artifact", "Not active until human approval is recorded."),
}

def read_manifest(path):
    lines = path.read_text().splitlines()
    fields = {}
    in_cert = False
    for line in lines:
        if line == "certification:": in_cert = True; continue
        if line and not line.startswith(" "): in_cert = False
        if line.startswith("builder_id:"): fields["id"] = line.split(":", 1)[1].strip()
        elif line.startswith("status:"): fields["manifest_status"] = line.split(":", 1)[1].strip()
        elif in_cert and line.startswith("  state:"): fields["certification"] = line.split(":", 1)[1].strip()
    return fields

entries=[]
for path in sorted(CERT.glob("*.yaml")):
    data=read_manifest(path); builder=data.get("id")
    if builder not in CATALOG: continue
    category,sandbox,output,limitations=CATALOG[builder]
    active=data.get("manifest_status") == "active"
    cert=data.get("certification", "unknown").replace("_", " ").upper()
    entries.append({"id":builder,"category":category,"version":"v1","status":"ACTIVE" if active else "DEVELOPMENT","certification":cert,"sandbox":sandbox,"output":output,"limitations":limitations})
OUT.write_text("/* Generated from vl/certification/*.yaml; do not edit manually. */\nwindow.VL_BUILDER_REGISTRY = " + json.dumps(entries, separators=(",",":")) + ";\n")
