import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parent / 'run_scheduled.py'
spec = importlib.util.spec_from_file_location('run_scheduled', MODULE)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


class ScheduledDirectorRunTests(unittest.TestCase):
    def test_manifest_binds_brief_to_source_snapshot_and_preserves_authority(self):
        brief = {
            'generated_at': '2026-09-17T00:17:00Z',
            'source_captured_at': '2026-09-17T00:45:00Z',
            'freshness_status': 'FRESH',
            'source_age_hours': 0.5,
        }
        manifest = rs.build_run_manifest(brief, 'abc123', '42', 'deadbeef')
        self.assertEqual(manifest['schema'], 'lom.director-brief-run/1')
        self.assertEqual(manifest['source_snapshot']['sha256'], 'abc123')
        self.assertEqual(manifest['source_snapshot']['freshness_status'], 'FRESH')
        self.assertEqual(manifest['github_run_id'], '42')
        self.assertEqual(manifest['github_sha'], 'deadbeef')
        self.assertEqual(manifest['execution_authority'], 'NONE')
        self.assertFalse(manifest['execution_performed'])
        self.assertEqual(manifest['production_authority'], 'HUMAN_ONLY')
        self.assertEqual(manifest['protected_main_merge'], 'HUMAN_ONLY')

    def test_sha256_file_is_deterministic_and_changes_with_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text(json.dumps({'a': 1}), encoding='utf-8')
            first = rs.sha256_file(path)
            second = rs.sha256_file(path)
            self.assertEqual(first, second)
            path.write_text(json.dumps({'a': 2}), encoding='utf-8')
            self.assertNotEqual(first, rs.sha256_file(path))


if __name__ == '__main__':
    unittest.main()
