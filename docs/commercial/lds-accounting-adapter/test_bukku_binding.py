import unittest
from bukku_binding import (
    BukkuBinding,BukkuConfig,BukkuRoute,
    STAGING_BASE_URL,PRODUCTION_BASE_URL,DOCUMENTED_RATE_LIMIT_PER_MINUTE,
)
from bukku_sandbox_gate import evaluate

def cfg(**kw):
    d=dict(
        environment="staging",
        access_token="sandbox-secret",
        company_subdomain="ld-sandbox",
        base_url=STAGING_BASE_URL,
    )
    d.update(kw)
    return BukkuConfig(**d)

class BukkuBindingTests(unittest.TestCase):
    def test_documented_rate_limit(self):
        self.assertEqual(DOCUMENTED_RATE_LIMIT_PER_MINUTE,600)

    def test_staging_config_passes(self):
        self.assertEqual(BukkuBinding(cfg()).readiness()["status"],"PASS")

    def test_production_environment_is_forbidden(self):
        r=BukkuBinding(cfg(environment="production",base_url=PRODUCTION_BASE_URL)).readiness()
        self.assertEqual(r["reason"],"PRODUCTION_ENVIRONMENT_FORBIDDEN_IN_P0")

    def test_wrong_staging_url_holds(self):
        self.assertEqual(
            BukkuBinding(cfg(base_url="https://example.invalid")).readiness()["reason"],
            "STAGING_BASE_URL_MISMATCH"
        )

    def test_missing_token_holds(self):
        self.assertEqual(
            BukkuBinding(cfg(access_token="")).readiness()["reason"],
            "BUKKU_ACCESS_TOKEN_REQUIRED"
        )

    def test_missing_subdomain_holds(self):
        self.assertEqual(
            BukkuBinding(cfg(company_subdomain="")).readiness()["reason"],
            "BUKKU_COMPANY_SUBDOMAIN_REQUIRED"
        )

    def test_headers_match_documented_contract(self):
        h=BukkuBinding(cfg()).headers()
        self.assertEqual(h["Authorization"],"Bearer sandbox-secret")
        self.assertEqual(h["Company-Subdomain"],"ld-sandbox")
        self.assertEqual(h["Accept"],"application/json")

    def test_unverified_route_fails_closed(self):
        r=BukkuBinding(cfg()).build_request(BukkuRoute("invoice","POST","/placeholder",False))
        self.assertEqual(r["reason"],"BUKKU_ROUTE_NOT_VERIFIED")

    def test_verified_request_builder_performs_no_network(self):
        r=BukkuBinding(cfg()).build_request(
            BukkuRoute("fixture","POST","/fixture",True,"test-only"),
            {"x":1}
        )
        self.assertEqual(r["status"],"PASS")
        self.assertFalse(r["network_call_performed"])
        self.assertTrue(r["url"].startswith(STAGING_BASE_URL))

    def test_token_is_redacted(self):
        self.assertEqual(BukkuBinding(cfg()).redacted_config()["access_token"],"***")

    def test_sandbox_gate_holds_until_routes_verified(self):
        r=evaluate(cfg())
        self.assertEqual(r["status"],"HOLD")
        self.assertEqual(r["reason"],"BUKKU_ROUTE_CAPABILITY_VERIFICATION_REQUIRED")
        self.assertGreater(len(r["unverified_routes"]),0)

if __name__=="__main__":
    unittest.main()
