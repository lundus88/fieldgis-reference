import copy
import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('validator', HERE / 'validate_canonical_chain.py')
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
BASE = json.loads((HERE / 'canonical-chain.json').read_text(encoding='utf-8'))


class CanonicalChainTests(unittest.TestCase):
    def test_current_manifest_passes(self):
        validator.validate(copy.deepcopy(BASE))

    def test_terminal_stage_is_6_12(self):
        self.assertEqual(BASE['canonical_stages'][-1]['id'], '6.12')
        self.assertEqual(BASE['pending_external_stages'], [])

    def test_missing_stage_fails(self):
        data = copy.deepcopy(BASE)
        data['canonical_stages'].pop(5)
        with self.assertRaises(SystemExit):
            validator.validate(data)

    def test_reordered_stage_fails(self):
        data = copy.deepcopy(BASE)
        data['canonical_stages'][5], data['canonical_stages'][6] = data['canonical_stages'][6], data['canonical_stages'][5]
        with self.assertRaises(SystemExit):
            validator.validate(data)

    def test_duplicate_stage_fails(self):
        data = copy.deepcopy(BASE)
        data['canonical_stages'].append(copy.deepcopy(data['canonical_stages'][0]))
        with self.assertRaises(SystemExit):
            validator.validate(data)

    def test_duplicate_owner_fails(self):
        data = copy.deepcopy(BASE)
        data['canonical_stages'][1]['owner'] = data['canonical_stages'][0]['owner']
        with self.assertRaises(SystemExit):
            validator.validate(data)

    def test_weakened_production_authority_fails(self):
        data = copy.deepcopy(BASE)
        data['authority']['production_authority'] = 'AUTO'
        with self.assertRaises(SystemExit):
            validator.validate(data)

    def test_self_approval_fails(self):
        data = copy.deepcopy(BASE)
        data['authority']['self_approval'] = 'ALLOWED'
        with self.assertRaises(SystemExit):
            validator.validate(data)

    def test_pending_stage_cannot_be_canonical(self):
        data = copy.deepcopy(BASE)
        data['pending_external_stages'] = [{
            'id': '7.0',
            'owner': 'future-stage',
            'tracking_pr': 999,
            'merge_required_before_canonical': True,
        }]
        data['canonical_stages'].append({
            'id': '7.0',
            'owner': 'future-stage',
            'artifact': data['canonical_stages'][0]['artifact'] + '.duplicate',
        })
        with self.assertRaises(SystemExit):
            validator.validate(data)

    def test_pending_stage_requires_merge_gate(self):
        data = copy.deepcopy(BASE)
        data['pending_external_stages'] = [{
            'id': '7.0',
            'owner': 'future-stage',
            'tracking_pr': 999,
            'merge_required_before_canonical': False,
        }]
        with self.assertRaises(SystemExit):
            validator.validate(data)


if __name__ == '__main__':
    unittest.main()
