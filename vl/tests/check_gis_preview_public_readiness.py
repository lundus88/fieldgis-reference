#!/usr/bin/env python3
from pathlib import Path
import sys

src = Path("vl/visual-preview/verify-factory-preview.mjs").read_text()

required = [
    "const previewOrigin = new URL(url).origin;",
    "sameOriginFailures",
    "externalFailures",
    "builderKey !== 'gis-web-v1' && externalFailures.length",
    "MapLibre runtime did not boot",
    "MapLibre canvas missing",
    "vl.visual-preview-evidence/3",
]

errors = [f"missing: {token}" for token in required if token not in src]

# Safety invariants: console errors and same-origin failures must remain fatal.
for token in [
    "if (consoleErrors.length) throw new Error",
    "if (sameOriginFailures.length)",
]:
    if token not in src:
        errors.append(f"fail-closed invariant missing: {token}")

# External failures may only be tolerated for GIS; web/PWA remain strict.
if "builderKey !== 'gis-web-v1'" not in src:
    errors.append("external-network exception is not GIS-scoped")

if errors:
    print("GIS preview public-readiness contract: FAIL")
    for e in errors:
        print("-", e)
    sys.exit(1)

print("GIS preview public-readiness contract: PASS")
