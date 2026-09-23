import unittest
from hashlib import sha256

from financebridge_binding import ProviderConfig
from provider_route_evidence import RouteEvidence,verify_registry
from provider_sandbox_golden import preflight,REQUIRED_OPERATIONS

DIGEST=sha256(b"fixture").hexdigest()

def cfg(**kw):
    d=dict(
        environment="staging",
        access_token="sandbox-secret",
        tenant_header_name="X-Tenant",
        tenant_key="tenant-fixture",
        base_url="https://sandbox.accounting-provider.invalid",
        rate_limit_per_minute=600,
    )
    d.update(kw)
    return ProviderConfig(**d)

def evidence(op,**kw):
    d=dict(
        operation=op,
        method="POST",
        path="/fixture/"+op,
        request_schema_digest=DIGEST,
        response_schema_digest=DIGEST,
        source_reference="private-evidence:fixture",
        verified_by="fixture-reviewer",
        verified_at="2026-09-23T00:00:00Z",
        staging_only=True,
    )
    d.update(kw)
    return RouteEvidence(**d)

class ProviderOnboardingTests(unittest.TestCase):
    def full_routes(self):
        return [evidence(op) for op in REQUIRED_OPERATIONS]

    def test_complete_route_registry_passes(self):
        self.assertEqual(
            verify_registry(REQUIRED_OPERATIONS,self.full_routes())["status"],
            "PASS"
        )

    def test_missing_route_holds(self):
        routes=self.full_routes()[:-1]
        r=verify_registry(REQUIRED_OPERATIONS,routes)
        self.assertEqual(r["reason"],"ROUTE_EVIDENCE_INCOMPLETE")

    def test_bad_schema_digest_holds(self):
        r=evidence("create_invoice",request_schema_digest="bad").validate()
        self.assertEqual(r["reason"],"REQUEST_SCHEMA_DIGEST_INVALID")

    def test_unzoned_timestamp_holds(self):
        r=evidence("create_invoice",verified_at="2026-09-23T00:00:00").validate()
        self.assertEqual(r["reason"],"VERIFIED_AT_TIMEZONE_REQUIRED")

    def test_production_route_evidence_holds(self):
        r=evidence("create_invoice",staging_only=False).validate()
        self.assertEqual(r["reason"],"PRODUCTION_ROUTE_EVIDENCE_FORBIDDEN_IN_P1")

    def test_preflight_passes_without_network(self):
        r=preflight(cfg(),self.full_routes())
        self.assertEqual(r["status"],"PASS")
        self.assertFalse(r["network_call_performed"])
        self.assertFalse(r["production_authority"])

    def test_preflight_fails_closed_without_token(self):
        r=preflight(cfg(access_token=""),self.full_routes())
        self.assertEqual(r["stage"],"CONFIG")
        self.assertEqual(r["status"],"HOLD")

if __name__=="__main__":
    unittest.main()
