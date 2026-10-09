"""No network, model credentials, or real papers are used by these tests."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_site import build
from validate_site import validate


def fixture(date='2020-01-01', complete=True):
    return dict(listing_date=date, published_at=date + 'T12:00:00+00:00',
                source_count=0, signal_title='TEST ONLY', signal='Synthetic test fixture',
                mind_model='TEST ONLY', papers=[], complete=complete)


class DirectPublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)

    def write(self, digest, filename=None):
        path = self.source / (filename or digest['listing_date'] + '.json')
        path.write_text(json.dumps(digest), encoding='utf-8')
        return path

    def test_empty_source(self):
        self.assertEqual(build(self.source)['digests'], [])

    def test_partial_does_not_advance_complete_cursor(self):
        self.write(fixture(complete=False))
        output = build(self.source)
        self.assertEqual(len(output['digests']), 1)
        self.assertIsNone(output['pipeline']['latest_generated_date'])
        self.assertEqual(output['pipeline']['state'], 'source_incomplete')
        output['pipeline']['latest_generated_date'] = '2020-01-01'
        with self.assertRaises(ValueError):
            validate(output)

    def test_newer_partial_preserves_prior_complete_cursor(self):
        self.write(fixture())
        self.write(fixture('2020-01-02', False))
        output = build(self.source)
        self.assertEqual(output['pipeline']['latest_generated_date'], '2020-01-01')
        self.assertEqual(output['digests'][0]['listing_date'], '2020-01-02')

    def test_complete_digest_advances_cursor_without_mutating_source(self):
        path = self.write(fixture())
        before = path.read_bytes()
        output = build(self.source)
        self.assertEqual(output['pipeline']['state'], 'generated')
        self.assertEqual(output['pipeline']['latest_generated_date'], '2020-01-01')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(output, build(self.source))

    def test_completeness_must_be_explicit_boolean(self):
        for value in (None, 'false', 0):
            digest = fixture()
            if value is None:
                del digest['complete']
            else:
                digest['complete'] = value
            self.write(digest)
            with self.subTest(value=value), self.assertRaises(ValueError):
                build(self.source)

    def test_filename_must_match_date(self):
        self.write(fixture(), '2020-01-02.json')
        with self.assertRaises(ValueError):
            build(self.source)

    def test_private_fields_rejected(self):
        digest = fixture()
        digest['conversation_notes'] = 'PRIVATE TEST FIXTURE'
        self.write(digest)
        with self.assertRaises(ValueError):
            build(self.source)

    def test_unexpected_filename_rejected(self):
        self.write(fixture(), 'backup.json')
        with self.assertRaises(ValueError):
            build(self.source)


if __name__ == '__main__':
    unittest.main()
