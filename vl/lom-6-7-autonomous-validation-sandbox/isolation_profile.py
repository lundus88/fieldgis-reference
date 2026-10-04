from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

SCHEMA = "lom.secure-ephemeral-sandbox/1"
AUTONOMOUS_CEILING = "PREPARE_PR"
EXECUTION_AUTHORITY = "NONE"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def canonical_profile() -> dict[str, Any]:
    body = {
        "schema": SCHEMA,
        "status": "NON_PRODUCTION",
        "workspace_mode": "EPHEMERAL_COPY",
        "host_workspace_direct_mount": False,
        "export_mode": "ALLOWLIST_ONLY",
        "export_symlink_policy": "FORBIDDEN",
        "network": "DISABLED",
        "credential_access": "NONE",
        "docker_socket": "FORBIDDEN",
        "root_filesystem": "READ_ONLY",
        "linux_capabilities": "ALL_DROPPED",
        "no_new_privileges": True,
        "special_host_files": "FORBIDDEN",
        "source_git_metadata": "EXCLUDED",
        "temporary_workspace_cleanup": "REQUIRED",
        "max_pids": 256,
        "max_memory_mb": 2048,
        "max_cpus": 2,
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "production_credentials": "FORBIDDEN",
        "production_execution": "DISABLED",
        "authority_widening": "DISABLED",
    }
    return {**body, "profile_digest": digest(body)}


def validate_profile(profile: dict[str, Any]) -> dict[str, str]:
    if not isinstance(profile, dict) or profile.get("schema") != SCHEMA:
        return {"status": "HOLD", "reason": "SANDBOX_PROFILE_SCHEMA_INVALID"}

    required = {
        "workspace_mode": "EPHEMERAL_COPY",
        "host_workspace_direct_mount": False,
        "export_mode": "ALLOWLIST_ONLY",
        "export_symlink_policy": "FORBIDDEN",
        "network": "DISABLED",
        "credential_access": "NONE",
        "docker_socket": "FORBIDDEN",
        "root_filesystem": "READ_ONLY",
        "linux_capabilities": "ALL_DROPPED",
        "no_new_privileges": True,
        "special_host_files": "FORBIDDEN",
        "source_git_metadata": "EXCLUDED",
        "temporary_workspace_cleanup": "REQUIRED",
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "execution_authority": EXECUTION_AUTHORITY,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "production_credentials": "FORBIDDEN",
        "production_execution": "DISABLED",
        "authority_widening": "DISABLED",
    }
    for key, expected in required.items():
        if profile.get(key) != expected:
            return {"status": "HOLD", "reason": f"SANDBOX_INVARIANT_WEAKENED:{key}"}

    if not isinstance(profile.get("max_pids"), int) or profile["max_pids"] < 1 or profile["max_pids"] > 256:
        return {"status": "HOLD", "reason": "SANDBOX_PID_LIMIT_INVALID"}
    if not isinstance(profile.get("max_memory_mb"), int) or profile["max_memory_mb"] < 64 or profile["max_memory_mb"] > 2048:
        return {"status": "HOLD", "reason": "SANDBOX_MEMORY_LIMIT_INVALID"}
    if not isinstance(profile.get("max_cpus"), int) or profile["max_cpus"] < 1 or profile["max_cpus"] > 2:
        return {"status": "HOLD", "reason": "SANDBOX_CPU_LIMIT_INVALID"}

    body = {k: v for k, v in profile.items() if k != "profile_digest"}
    if profile.get("profile_digest") != digest(body):
        return {"status": "HOLD", "reason": "SANDBOX_PROFILE_DIGEST_MISMATCH"}
    return {"status": "READY", "reason": "SECURE_EPHEMERAL_SANDBOX_PROFILE_VALID"}
