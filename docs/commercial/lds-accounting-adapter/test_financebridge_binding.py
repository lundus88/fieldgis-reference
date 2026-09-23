import unittest
from financebridge_binding import FinanceBridgeBinding,ProviderConfig,ProviderRoute
from provider_sandbox_gate import evaluate

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

class FinanceBridgeBindingTests(unittest.TestCase):
    def test_staging_config_passes(self):
        self.assertEqual(FinanceBridgeBinding(cfg()).readiness()["status"],"PASS")

    def test_production_environment_is_forbidden(self):
        self.assertEqual(
            FinanceBridgeBinding(cfg(environment="production")).readiness()["reason"],
            "PRODUCTION_ENVIRONMENT_FORBIDDEN_IN_P0"
        )

    def test_https_staging_url_required(self):
        self.assertEqual(
            FinanceBridgeBinding(cfg(base_url="http://example.invalid")).readiness()["reason"],
            "STAGING_BASE_URL_REQUIRED"
        )

    def test_missing_token_holds(self):
        self.assertEqual(
            FinanceBridgeBinding(cfg(access_token="")).readiness()["reason"],
            "PROVIDER_ACCESS_TOKEN_REQUIRED"
        )

    def test_incomplete_tenant_header_holds(self):
        self.assertEqual(
            FinanceBridgeBinding(cfg(tenant_key="")).readiness()["reason"],
            "TENANT_HEADER_CONFIGURATION_INCOMPLETE"
        )

    def test_rate_limit_required(self):
        self.assertEqual(
            FinanceBridgeBinding(cfg(rate_limit_per_minute=0)).readiness()["reason"],
            "PROVIDER_RATE_LIMIT_REQUIRED"
        )

    def test_headers_are_provider_neutral(self):
        h=FinanceBridgeBinding(cfg()).headers()
        self.assertEqual(h["Authorization"],"Bearer sandbox-secret")
        self.assertEqual(h["X-Tenant"],"tenant-fixture")

    def test_unverified_route_fails_closed(self):
        r=FinanceBridgeBinding(cfg()).build_request(ProviderRoute("invoice","POST","/placeholder",False))
        self.assertEqual(r["reason"],"PROVIDER_ROUTE_NOT_VERIFIED")

    def test_verified_request_builder_performs_no_network(self):
        r=FinanceBridgeBinding(cfg()).build_request(
            ProviderRoute("fixture","POST","/fixture",True,"test-only"),{"x":1}
        )
        self.assertEqual(r["status"],"PASS")
        self.assertFalse(r["network_call_performed"])

    def test_sensitive_config_is_redacted(self):
        c=FinanceBridgeBinding(cfg()).redacted_config()
        self.assertEqual(c["access_token"],"***")
        self.assertEqual(c["tenant_key"],"***")

    def test_sandbox_gate_holds_until_routes_verified(self):
        r=evaluate(cfg())
        self.assertEqual(r["status"],"HOLD")
        self.assertEqual(r["reason"],"PROVIDER_ROUTE_CAPABILITY_VERIFICATION_REQUIRED")

if __name__=="__main__":
    unittest.main()
