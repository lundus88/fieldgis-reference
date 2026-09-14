"""Static guard for Issue #211; PostgreSQL behaviour is tested separately."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / 'vl/migrations/20260914_harden_public_security_definer_rpc.sql').read_text()
HISTORY = ROOT / 'vl/migrations'


def function(source, name):
    match = re.search(r'create or replace function\s+' + re.escape(name)
                      + r'\s*\(.*?\$\$;', source, re.S | re.I)
    assert match, f'missing function: {name}'
    return match.group()


class RpcBoundaryContract(unittest.TestCase):
    def test_public_signatures_are_explicit_invokers(self):
        expected = {
            'request_vrs_internal_usage_override': ['p_project_id uuid', 'p_reason text', 'p_duration_minutes integer default 60'],
            'vl_get_assisted_build_quote': ['p_complexity text'],
            'vl_prepare_assisted_build_product_alignment': ['p_answers jsonb', 'p_structured jsonb'],
        }
        for name, args in expected.items():
            text = function(SQL, 'public.' + name)
            self.assertIn('security invoker', text)
            self.assertNotIn('security definer', text)
            self.assertIn("set search_path = ''", text)
            self.assertIn('auth.uid()', text)
            self.assertIn('returns jsonb', text)
            for arg in args:
                self.assertIn(arg, text)

    def test_no_client_executable_privileged_helper_grant(self):
        self.assertIn('revoke all on function private.request_vrs_internal_usage_override_impl() from public, anon, authenticated, service_role;', SQL)
        self.assertNotRegex(SQL, r'(?i)grant\s+execute\s+on\s+function\s+private\.request_vrs_internal_usage_override_impl')
        helper = function(SQL, 'private.request_vrs_internal_usage_override_impl')
        self.assertIn('returns trigger', helper)
        self.assertIn('security definer', helper)
        self.assertIn("set search_path = ''", helper)

    def test_every_override_authorization_check_precedes_both_writes(self):
        helper = function(SQL, 'private.request_vrs_internal_usage_override_impl')
        first_write = helper.index('insert into private.internal_usage_overrides')
        for token in ["tg_table_schema <> 'private'", "tg_table_name <> 'internal_usage_override_request'",
                      'v_uid is null', "v_aal <> 'aal2'", 'new.duration_minutes is null',
                      'new.duration_minutes < 1', 'new.duration_minutes > 240',
                      "length(btrim(coalesce(new.reason,''))) < 12",
                      'pm.project_id=new.project_id', 'pm.user_id=v_uid', "pm.role in ('owner','admin')"]:
            self.assertLess(helper.index(token), first_write)
        self.assertIn('insert into private.internal_usage_audit', helper)
        self.assertIn('now()+make_interval(mins=>new.duration_minutes)', helper)
        for flag in ['production_approval_changed', 'production_promotion_changed',
                     'production_approval_bypassed', 'production_promotion_bypassed']:
            self.assertIn(f"'{flag}',false", helper)

    def test_private_insert_interface_does_not_store_or_disclose_records(self):
        view = SQL.split('create or replace view private.internal_usage_override_request', 1)[1].split(';', 1)[0]
        self.assertIn('where false', view)
        self.assertNotRegex(view, r'(?i)\bfrom\s+')
        self.assertIn('grant insert (project_id, reason, duration_minutes), select (result)', SQL)
        self.assertIn('instead of insert on private.internal_usage_override_request', SQL)

    def test_quote_is_stable_and_exposes_only_the_existing_contract(self):
        facade = function(SQL, 'public.vl_get_assisted_build_quote')
        self.assertIn('\nstable\n', facade)
        self.assertNotRegex(facade, r'(?i)\b(insert into|update|delete from)\b')
        view = SQL.split('create or replace view private.assisted_build_quote_catalog', 1)[1].split(';', 1)[0]
        self.assertIn('security_barrier = true', view)
        self.assertIn('policy.enabled=true and auth.uid() is not null', view)
        self.assertNotIn('policy.*', view)
        self.assertNotIn('updated_at', view)
        self.assertNotRegex(SQL, r'(?i)grant\s+.*\bon\s+(?:table\s+)?private\.assisted_build_cost_policy')

    def test_alignment_generator_body_is_preserved_except_equivalent_hash_primitive(self):
        source = (HISTORY / '20260901_assisted_build_product_alignment.sql').read_text()
        before = function(source, 'private.build_assisted_build_product_alignment')
        after = function(SQL, 'private.build_assisted_build_product_alignment')
        before = before.replace('security definer', 'security invoker').replace(
            'set search_path=private,public,auth,extensions,pg_temp', "set search_path = ''")
        for variable in ['v_fi', 'v_cert_input']:
            before = before.replace(f"digest(convert_to({variable}::text,'UTF8'),'sha256')",
                                    f"pg_catalog.sha256(convert_to({variable}::text,'UTF8'))")
        self.assertEqual(after, before)
        self.assertNotRegex(after, r'(?i)\b(insert into|update|delete from)\b')

    def test_alignment_validation_and_review_contract_are_retained(self):
        facade = function(SQL, 'public.vl_prepare_assisted_build_product_alignment')
        for token in ['private.build_assisted_build_product_alignment(p_answers,p_structured)',
                      'private.validate_product_alignment(v_alignment)',
                      "'generated_for_review',true", "'production_approval_performed',false",
                      "'production_promotion_performed',false"]:
            self.assertIn(token, facade)
        self.assertIn('alter function private.validate_product_alignment(jsonb) security invoker;', SQL)
        self.assertIn('revoke all on function private.validate_product_alignment(jsonb) from public, anon;', SQL)

    def test_only_override_and_audit_storage_can_be_mutated(self):
        targets = set(re.findall(r'\b(?:insert\s+into|update|delete\s+from)\s+((?:public|private)\.\w+)', SQL, re.I))
        self.assertEqual(targets, {'private.internal_usage_override_request',
                                 'private.internal_usage_overrides', 'private.internal_usage_audit'})
        self.assertNotRegex(SQL, r'(?i)\b(?:create or replace|alter) function public\.(?:evaluate_vrs|approve_vrs|claim_vrs|complete_vrs)')
        self.assertNotRegex(SQL, r'(?i)(?:production_approval|production_promotion)\w*\s*\x27?\s*,\s*true')
        self.assertNotRegex(SQL, r'(?i)\b(?:disable row level security|set role|set session authorization)\b')

    def test_transaction_and_replay_revoke_column_grants(self):
        self.assertRegex(SQL, r'(?m)^begin;$')
        self.assertTrue(SQL.rstrip().endswith('commit;'))
        self.assertIn('revoke all (project_id, reason, duration_minutes, result)', SQL)
        self.assertIn('revoke all (complexity_class, quote)', SQL)
        self.assertIn("has_any_column_privilege(v_role,v_table,'SELECT,INSERT,UPDATE,REFERENCES')", SQL)

    def test_assisted_ui_named_rpc_arguments_and_production_lock_are_retained(self):
        ui = (ROOT / 'vl/public/assisted-build.html').read_text()
        for token in ['/rest/v1/rpc/vl_get_assisted_build_quote', '{p_complexity:complexity}',
                      '/rest/v1/rpc/vl_prepare_assisted_build_product_alignment', '{p_answers:a,p_structured:s}',
                      "status:'draft'", 'production_locked:true', 'product_alignment:lastDraft.product_alignment']:
            self.assertIn(token, ui)


if __name__ == '__main__':
    unittest.main(verbosity=2)
