"""Historical analysis is readable but never becomes an official completion record."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_site import build, history_digests


def fixture():
    return {'schema_version': 1, 'kind': 'public_daily_analysis_archive',
            'imported_at': '2020-02-02T00:00:00+00:00', 'reports': [{
                'report_date': '2020-01-02', 'reported_listing_date': '2020-01-01',
                'title': 'TEST ONLY', 'signal': 'Synthetic test analysis', 'mind_model': 'Question',
                'papers': [{'id': '2001.00001', 'title': 'TEST ONLY', 'status': 'new',
                            'tags': ['systems'], 'priority': True, 'analysis': 'Test',
                            'problem': 'Test', 'mapping': 'Test', 'reported_version': 'v2'}]}]}


class HistoryArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)
        (self.source / 'history').mkdir()
        self.path = self.source / 'history' / 'test.json'

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding='utf-8')

    def test_absent_history_is_backward_compatible(self):
        self.assertEqual(build(self.source)['digests'], [])

    def test_dates_are_preserved_but_not_completed(self):
        self.write(fixture())
        out = build(self.source)
        self.assertEqual(out['digests'][0]['listing_date'], '2020-01-02')
        self.assertIn('2020-01-01', out['digests'][0]['signal'])
        self.assertFalse(out['digests'][0]['complete'])
        self.assertIsNone(out['pipeline']['latest_generated_date'])

    def test_metadata_does_not_become_verified(self):
        self.write(fixture())
        p = build(self.source)['digests'][0]['papers'][0]
        self.assertEqual(p['version'], '')
        self.assertEqual(p['institution'], 'Unknown')
        self.assertIsNone(p['code_url'])
        self.assertIn('v2', p['evidence'])
        self.assertIn('本次未复核', p['sources'][0]['label'])

    def test_rebuild_is_idempotent_and_read_only(self):
        self.write(fixture()); before = self.path.read_bytes()
        self.assertEqual(build(self.source), build(self.source))
        self.assertEqual(self.path.read_bytes(), before)

    def test_direct_date_file_wins_without_mutation(self):
        self.write(fixture())
        direct = build(self.source)['digests'][0]
        direct['complete'] = True; direct['signal_title'] = 'Authoritative direct file'
        path = self.source / '2020-01-02.json'; path.write_text(json.dumps(direct))
        before = path.read_bytes(); out = build(self.source)
        self.assertEqual(len(out['digests']), 1)
        self.assertEqual(out['digests'][0], direct)
        self.assertEqual(out['pipeline']['latest_generated_date'], '2020-01-02')
        self.assertEqual(path.read_bytes(), before)

    def test_incomplete_direct_file_also_wins(self):
        self.write(fixture())
        direct = build(self.source)['digests'][0]; direct['signal_title'] = 'Pending direct file'
        (self.source / '2020-01-02.json').write_text(json.dumps(direct))
        out = build(self.source)
        self.assertEqual(out['digests'][0]['signal_title'], 'Pending direct file')
        self.assertIsNone(out['pipeline']['latest_generated_date'])

    def test_reject_private_export_kind(self):
        data = fixture(); data['kind'] = 'conversation_history'; self.write(data)
        with self.assertRaises(ValueError): build(self.source)

    def test_reject_private_fields_at_each_level(self):
        for level in ('root', 'report', 'paper'):
            data = fixture()
            target = data if level == 'root' else data['reports'][0] if level == 'report' else data['reports'][0]['papers'][0]
            target['private_notes'] = 'DO NOT PUBLISH'; self.write(data)
            with self.subTest(level=level), self.assertRaises(ValueError): build(self.source)

    def test_duplicate_dates_rejected(self):
        data = fixture(); data['reports'] *= 2; self.write(data)
        with self.assertRaises(ValueError): build(self.source)

    def test_duplicate_dates_across_shards_rejected(self):
        self.write(fixture()); (self.path.parent / 'another.json').write_bytes(self.path.read_bytes())
        with self.assertRaises(ValueError): build(self.source)

    def test_duplicate_paper_in_same_report_rejected(self):
        data = fixture(); data['reports'][0]['papers'] *= 2; self.write(data)
        with self.assertRaises(ValueError): build(self.source)

    def test_same_paper_across_dates_is_retained(self):
        data = fixture(); r = copy.deepcopy(data['reports'][0]); r['report_date'] = '2020-01-03'
        data['reports'].append(r); self.write(data)
        self.assertEqual(len(build(self.source)['digests']), 2)

    def test_missing_id_and_invalid_priority_rejected(self):
        for field, value in [('id', None), ('id', 'javascript:evil'), ('priority', 1)]:
            data = fixture(); data['reports'][0]['papers'][0][field] = value; self.write(data)
            with self.subTest(field=field, value=value), self.assertRaises(ValueError): build(self.source)

    def test_untrusted_completion_field_rejected(self):
        data = fixture(); data['reports'][0]['complete'] = True; self.write(data)
        with self.assertRaises(ValueError): build(self.source)

    def test_symlink_source_rejected(self):
        self.write(fixture()); target = self.source / 'original.json'; self.path.rename(target); self.path.symlink_to(target)
        with self.assertRaises(ValueError): build(self.source)

    def test_real_migration_inventory(self):
        directory = ROOT / 'data' / 'digests' / 'history'
        docs = [r for file in sorted(directory.glob('*.json')) for r in history_digests(file)]
        self.assertEqual(len(docs), 12)
        self.assertEqual(sum(len(d['papers']) for d in docs), 156)
        self.assertEqual(len({p['arxiv_id'] for d in docs for p in d['papers']}), 152)
        self.assertTrue(all(not d['complete'] for d in docs))
        self.assertEqual(min(d['listing_date'] for d in docs), '2026-09-18')
        self.assertEqual(max(d['listing_date'] for d in docs), '2026-10-07')


if __name__ == '__main__':
    unittest.main()
