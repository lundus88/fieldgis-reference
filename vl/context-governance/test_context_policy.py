#!/usr/bin/env python3
import json
import unittest
from pathlib import Path
from validate_context_policy import validate_policy, decide

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT / 'default-context-policy.json').read_text())


class ContextGovernanceTests(unittest.TestCase):
    def test_default_policy_validates(self):
        self.assertTrue(validate_policy(POLICY))

    def test_known_source_path_can_be_allowed(self):
        result = decide(POLICY, 'repo_path', 'src/ui/app.ts', 'source_code')
        self.assertEqual(result['decision'], 'allow')

    def test_unknown_path_fails_closed(self):
        result = decide(POLICY, 'repo_path', 'docs/internal-plan.md', 'internal_document')
        self.assertEqual(result['decision'], 'deny')
        self.assertIn('default deny', result['reason'])

    def test_env_file_is_denied_even_if_data_class_is_source(self):
        result = decide(POLICY, 'repo_path', 'src/.env.production', 'source_code')
        self.assertEqual(result['decision'], 'deny')
        self.assertIn('deny-secrets', result['rule_ids'])

    def test_secret_directory_is_denied(self):
        result = decide(POLICY, 'repo_path', 'src/secrets/token.txt', 'source_code')
        self.assertEqual(result['decision'], 'deny')

    def test_sensitive_class_never_becomes_allowed_by_generic_rule(self):
        result = decide(POLICY, 'repo_path', 'src/customer.json', 'customer_private')
        self.assertEqual(result['decision'], 'deny')

    def test_production_connector_resource_is_denied(self):
        result = decide(POLICY, 'connector_resource', 'production/database/customers', 'production_data')
        self.assertEqual(result['decision'], 'deny')

    def test_policy_without_default_deny_is_invalid(self):
        bad = json.loads(json.dumps(POLICY))
        bad['default_decision'] = 'allow'
        with self.assertRaisesRegex(ValueError, 'default_decision must be deny'):
            validate_policy(bad)

    def test_audit_must_never_record_secret_values(self):
        bad = json.loads(json.dumps(POLICY))
        bad['audit']['record_secret_values'] = True
        with self.assertRaisesRegex(ValueError, 'record_secret_values must be false'):
            validate_policy(bad)


if __name__ == '__main__':
    unittest.main()
