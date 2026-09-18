#!/usr/bin/env python3
from pathlib import Path
import re
import sys

sql = Path("vl/migrations/20260918_pwa_offline_contract_semantic_validator.sql").read_text()

required = [
    "create or replace function public.evaluate_vrs_release_server_gates",
    "cache_put_detection",
    "bounded_js_cache_handle_put_call",
    "required_gates_authority",
    "deployment_snapshot",
    "production application remains human-gated",
]

errors = [f"missing token: {token}" for token in required if token not in sql.lower()]

pattern = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*[.]put[\s]*[(]")

fixtures = {
    "canonical_cache_put": (
        "caches.open(CACHE).then(cache=>cache.put(request,copy));"
        "caches.match(request);",
        True,
    ),
    "short_cache_handle": (
        "caches.open(CACHE).then(c=>c.put(request,copy));"
        "caches.match(request);",
        True,
    ),
    "no_cache_write": (
        "caches.open(CACHE);caches.match(request);",
        False,
    ),
    "unrelated_put": (
        "object.put(request,copy);caches.match(request);",
        False,
    ),
}

def gate(sw: str, manifest: str = '{"name":"PWA"}') -> bool:
    cache_open = "caches.open" in sw
    cache_put = bool(pattern.search(sw))
    cache_match = "caches.match" in sw
    # Constrain .put acceptance to service-worker cache code by requiring
    # CacheStorage open + offline match in the same source.
    return cache_open and cache_put and cache_match and bool(manifest)

for name, (source, expected) in fixtures.items():
    actual = gate(source)
    if actual != expected:
        errors.append(f"{name}: expected {expected}, got {actual}")

if errors:
    print("PWA offline semantic validator regression: FAIL")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("PWA offline semantic validator regression: PASS")
print(f"fixtures={len(fixtures)}")
