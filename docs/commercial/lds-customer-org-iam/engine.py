#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Dict

ROLE_ACTIONS={
"OWNER":{"read","manage_org","manage_billing","manage_project","manage_technical"},
"FINANCE":{"read","manage_billing"},
"PROJECT_MANAGER":{"read","manage_project"},
"TECHNICAL":{"read","manage_technical"},
"VIEWER":{"read"}
}

@dataclass(frozen=True)
class AccessRequest:
    actor_org:str
    resource_org:str
    role:str
    action:str

def authorize(r:AccessRequest)->Dict:
    if not r.actor_org or r.actor_org != r.resource_org:
        return {"decision":"DENY","reason":"TENANT_BOUNDARY"}
    allowed=ROLE_ACTIONS.get(r.role,set())
    if r.action not in allowed:
        return {"decision":"DENY","reason":"ROLE_NOT_AUTHORIZED"}
    return {"decision":"ALLOW","reason":"ROLE_POLICY","audit_required":r.action!="read"}

def default_allow()->bool:
    return False
