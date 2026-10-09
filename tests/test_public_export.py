"""Offline schema and publication-boundary regression tests."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_site', ROOT / 'scripts/validate_site.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def example():
    # Synthetic test data. Never copied to site/ or published as a real paper.
    paper = dict(arxiv_id='2001.00001', version='v1', status='new', title='TEST ONLY',
                 summary='Synthetic fixture', tags=['systems'], read_now=True,
                 institution='Unknown', code_url=None, systems_problem='test',
                 mapping='test', evidence='Not scientific evidence',
                 sources=[dict(label='Fixture URL', url='https://arxiv.org/abs/2001.00001v1')])
    return dict(schema_version=1, generation_status='not_configured',
                digests=[dict(listing_date='2020-01-01', published_at='2020-01-02T10:00:00+08:00',
                              source_count=1, signal_title='Test', signal='Test',
                              mind_model='Test', papers=[paper])])


class PublicExportTests(unittest.TestCase):
    def test_empty_initial_export(self):
        module.validate(dict(schema_version=1, generation_status='not_configured', digests=[]))

    def test_valid_digest(self):
        module.validate(example())

    def test_private_fields_rejected(self):
        for field in ('notes', 'auth', 'conversation', 'feedback'):
            data = example()
            data['digests'][0]['papers'][0][field] = 'private'
            with self.subTest(field=field), self.assertRaises(ValueError):
                module.validate(data)

    def test_duplicate_batch_rejected(self):
        data = example()
        data['digests'].append(copy.deepcopy(data['digests'][0]))
        with self.assertRaises(ValueError): module.validate(data)

    def test_duplicate_paper_rejected(self):
        data = example()
        data['digests'][0]['source_count'] = 2
        data['digests'][0]['papers'] *= 2
        with self.assertRaises(ValueError): module.validate(data)

    def test_count_mismatch_rejected(self):
        data = example()
        data['digests'][0]['source_count'] = 0
        with self.assertRaises(ValueError): module.validate(data)

    def test_unsafe_link_rejected(self):
        for link in ('javascript:alert(1)', 'http://example.com', 'https://token@example.com'):
            data = example()
            data['digests'][0]['papers'][0]['code_url'] = link
            with self.subTest(link=link), self.assertRaises(ValueError): module.validate(data)

    def test_wrong_source_rejected(self):
        data = example()
        data['digests'][0]['papers'][0]['sources'][0]['url'] = 'https://arxiv.org/abs/2001.00002'
        with self.assertRaises(ValueError): module.validate(data)

    def test_timezone_required(self):
        data = example()
        data['digests'][0]['published_at'] = '2020-01-02T10:00:00'
        with self.assertRaises(ValueError): module.validate(data)

    def test_unknown_version_allowed(self):
        data = example()
        data['digests'][0]['papers'][0]['version'] = ''
        module.validate(data)

    def test_private_file_not_packaged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'index.html').write_text('test')
            (path / 'digests.json').write_text(json.dumps(example()))
            module.validate_site(path)
            (path / 'owner.key').write_text('TEST ONLY')
            with self.assertRaises(ValueError): module.validate_site(path)

    def test_real_public_directory(self):
        module.validate_site(ROOT / 'site')


if __name__ == '__main__':
    unittest.main()
