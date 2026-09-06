#!/usr/bin/env python3
import json
import unittest
from pathlib import Path
from build_context_manifest import build_context

ROOT = Path(__file__).resolve().parent
POLICY = json.loads((ROOT / 'default-context-policy.json').read_text())


class ContextManifestTests(unittest.TestCase):
    def test_denied_resources_do_not_enter_context(self):
        resources = [
            {'resource_type':'repo_path','resource':'src/ui/app.ts','data_class':'source_code','content':'export const ok = true;'},
            {'resource_type':'repo_path','resource':'src/.env.production','data_class':'source_code','content':'SECRET=do-not-log'},
            {'resource_type':'connector_resource','resource':'production/database/customers','data_class':'production_data','content':'private customer row'},
        ]
        result = build_context(POLICY, resources)
        self.assertEqual(len(result['context']), 1)
        self.assertEqual(result['context'][0]['resource'], 'src/ui/app.ts')
        serialized = json.dumps(result['manifest'])
        self.assertNotIn('do-not-log', serialized)
        self.assertNotIn('private customer row', serialized)
        self.assertEqual(result['manifest']['denied_count'], 2)
        self.assertFalse(result['manifest']['secret_values_recorded'])

    def test_manifest_records_hashes_not_denied_content(self):
        secret = 'TOP-SECRET-CONTENT'
        result = build_context(POLICY, [
            {'resource_type':'repo_path','resource':'src/secrets/key.txt','data_class':'secret','content':secret}
        ])
        self.assertEqual(result['context'], [])
        record = result['manifest']['resource_decisions'][0]
        self.assertEqual(record['decision'], 'deny')
        self.assertEqual(len(record['content_sha256']), 64)
        self.assertNotIn(secret, json.dumps(result['manifest']))

    def test_unknown_resource_fails_closed_and_is_excluded(self):
        result = build_context(POLICY, [
            {'resource_type':'prompt_attachment','resource':'unknown.bin','data_class':'unknown','content':'opaque'}
        ])
        self.assertEqual(result['context'], [])
        self.assertEqual(result['manifest']['resource_decisions'][0]['decision'], 'deny')


if __name__ == '__main__':
    unittest.main()
