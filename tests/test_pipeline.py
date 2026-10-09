"""No network or real keys: exercise source gates, idempotency, and resumable generation."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect_arxiv import NEW_URL, RECENT_URL, PipelineError, check_freshness, parse_listing, get_html, enrich
from update_digest import run, checked_results, Gemini, MAX_CALLS_DAY
from validate_site import validate

NOW = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
RECENT = '<h3>Fri, 9 Oct 2026 (showing 2 of 2 entries)</h3>'
ABSTRACT = 'This test system reduces memory traffic through an explicitly scheduled transfer pipeline.'
ENV = {'INBOX_GENERATION_ENABLED': 'true', 'INBOX_GEMINI_API_KEY': 'TEST-ONLY-NOT-A-KEY'}


def listing(day='Friday, 9 October 2026', count=3):
    parts = [f'<h3>Showing new listings for {day}</h3><p>Total of {count} entries</p>']
    for i, status in enumerate(['New submissions', 'Cross-lists', 'Replacements'], 1):
        parts.append(f'<h3>{status} (showing 1 of 1 entries)</h3><dl><dt><a href="/abs/2610.0000{i}">arXiv:2610.0000{i}</a></dt>'
                     f'<dd><div class="list-title">Title: TEST ONLY {i}</div><div class="list-authors"><a>Test Author</a></div>'
                     f'<div class="list-subjects">Test (cs.DC)</div><p class="mathjax">{ABSTRACT}</p></dd></dl>')
    return ''.join(parts)


def fetched(url):
    if url == NEW_URL: return listing()
    if url == RECENT_URL: return RECENT
    raise AssertionError('Unexpected network request')


def model(instruction, payload):
    if '"papers"' not in instruction:
        return {'title': '测试信号', 'body': '仅用于离线测试的因果链。', 'mind_model': '如何验证计算与通信的边界？'}
    return {'papers': [{'arxiv_id': p['arxiv_id'], 'include': True, 'reason': '测试系统机制',
                       'summary': '这是一项离线测试。没有真实实验结论。', 'systems_problem': '内存访问的系统问题。',
                       'mapping': '可能用于测试运行时接口，尚未验证。', 'institution': 'Unknown', 'code_url': None,
                       'tags': ['memory'], 'evidence_quote': ABSTRACT, 'limitations': '仅依据测试摘要，未验证真实结果。'} for p in payload]}


class ParserTests(unittest.TestCase):
    def test_sections_and_unknown_versions(self):
        b = parse_listing(listing())
        self.assertEqual(b['listing_date'], '2026-10-09')
        self.assertEqual(b['counts'], {'new': 1, 'cross-list': 1, 'revised': 1})
        self.assertEqual([p['version'] for p in b['papers']], ['', '', ''])

    def test_count_mismatch(self):
        with self.assertRaises(PipelineError): parse_listing(listing(count=12))

    def test_partial_sections(self):
        with self.assertRaises(PipelineError): parse_listing(listing().replace('showing 1 of 1', 'showing 1 of 2', 1))

    def test_error_page(self):
        with self.assertRaises(PipelineError): parse_listing('<h1>429</h1>')

    def test_missing_metadata(self):
        with self.assertRaises(PipelineError): parse_listing(listing().replace('list-title', 'broken', 1))

    def test_missing_section_count(self):
        with self.assertRaises(PipelineError): parse_listing(listing().replace('(showing 1 of 1 entries)', '', 1))

    def test_new_recent_disagree(self):
        with self.assertRaisesRegex(PipelineError, 'source_dates_disagree'):
            check_freshness(parse_listing(listing()), RECENT.replace('9 Oct', '8 Oct'), NOW)

    def test_stale_page(self):
        with self.assertRaisesRegex(PipelineError, 'source_stale'):
            check_freshness(parse_listing(listing('Monday, 10 August 2026')), '<h3>Mon, 10 Aug 2026</h3>', NOW)

    def test_weekend_not_wall_date(self):
        check_freshness(parse_listing(listing()), RECENT, datetime(2026, 10, 11, tzinfo=timezone.utc))

    def test_future_page_rejected(self):
        with self.assertRaisesRegex(PipelineError, 'source_stale'):
            check_freshness(parse_listing(listing()), RECENT, datetime(2026, 10, 8, tzinfo=timezone.utc))

    def test_arbitrary_source_rejected(self):
        for url in ['http://arxiv.org/list/cs.DC/new', 'https://arxiv.org.evil.test/abs/2610.00001', 'https://user@arxiv.org/abs/2610.00001']:
            with self.subTest(url=url), self.assertRaises(PipelineError): get_html(url)

    def test_duplicate_latest_version(self):
        html = listing().replace('/abs/2610.00001', '/abs/2610.00001v1').replace('/abs/2610.00003', '/abs/2610.00001v2')
        b = parse_listing(html)
        self.assertEqual(len(b['papers']), 2)
        self.assertEqual(b['papers'][0]['version'], 'v2')

    def test_duplicate_unknown_rejected(self):
        with self.assertRaises(PipelineError): parse_listing(listing().replace('2610.00003', '2610.00001'))


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root/'site').mkdir()
        (self.root/'site/digests.json').write_text(json.dumps({'schema_version': 1,'generation_status':'not_configured','digests':[]}))

    def tearDown(self): self.temp.cleanup()
    def export(self): return json.loads((self.root/'site/digests.json').read_text())
    def execute(self, fetch=fetched, call=model, env=ENV):
        return run(self.root, fetch, call, env, NOW)

    def test_collect_without_secret_never_calls_model(self):
        def forbidden(*args): raise AssertionError('model called without authorization')
        self.assertEqual(self.execute(call=forbidden, env={}), 'waiting_model')
        data = self.export()
        self.assertEqual(data['pipeline']['source_count'], 3)
        self.assertEqual(data['digests'], [])
        self.assertIsNone(data['pipeline']['latest_generated_date'])

    def test_secret_without_opt_in_is_disabled(self):
        self.assertEqual(self.execute(env={'INBOX_GEMINI_API_KEY':'TEST ONLY'}), 'waiting_model')

    def test_valid_analysis_generates(self):
        self.assertEqual(self.execute(), 'generated')
        data = self.export(); validate(data)
        self.assertEqual(len(data['digests'][0]['papers']), 3)
        self.assertEqual(data['pipeline']['latest_generated_date'], '2026-10-09')

    def test_same_batch_no_second_model_call(self):
        self.execute()
        def forbidden(*args): raise AssertionError('duplicate call')
        self.assertEqual(self.execute(call=forbidden), 'no_new')
        self.assertEqual(len(self.export()['digests']), 1)

    def test_network_failure_preserves_previous_digest(self):
        self.execute(); before = copy.deepcopy(self.export()['digests'])
        def fail(url): raise PipelineError('source_unavailable')
        self.assertEqual(self.execute(fetch=fail), 'source_error')
        self.assertEqual(self.export()['digests'], before)

    def test_partial_source_does_not_advance_cursor(self):
        self.assertEqual(self.execute(fetch=lambda u: listing(count=10) if u == NEW_URL else RECENT), 'source_incomplete')
        self.assertEqual(self.export()['digests'], [])

    def test_model_failure_preserves_empty_site(self):
        def fail(*args): raise PipelineError('model_error')
        self.assertEqual(self.execute(call=fail), 'model_error')
        self.assertEqual(self.export()['digests'], [])

    def test_failed_signal_resumes_cached_papers(self):
        def stop_after_papers(instruction, payload):
            if '"papers"' not in instruction: raise PipelineError('waiting_quota')
            return model(instruction, payload)
        self.assertEqual(self.execute(call=stop_after_papers), 'waiting_quota')
        self.assertEqual(self.export()['digests'], [])
        calls = []
        def resume(instruction, payload):
            calls.append(instruction); return model(instruction, payload)
        self.assertEqual(self.execute(call=resume), 'generated')
        self.assertEqual(len(calls), 1)

    def test_cosmetic_source_change_preserves_cache(self):
        def stop(instruction, payload):
            if '"papers"' not in instruction: raise PipelineError('waiting_quota')
            return model(instruction, payload)
        self.execute(call=stop)
        calls = []
        def resumed(instruction, payload): calls.append(instruction); return model(instruction, payload)
        self.assertEqual(self.execute(fetch=lambda u: '<!-- cosmetic -->' + fetched(u), call=resumed), 'generated')
        self.assertEqual(len(calls), 1)

    def test_unverified_url_fails_closed(self):
        def bad(instruction, payload):
            data = model(instruction, payload)
            data['papers'][0]['code_url'] = 'https://github.com/not-verified/example'
            return data
        self.assertEqual(self.execute(call=bad), 'model_error')
        self.assertEqual(self.export()['digests'], [])

    def test_unsupported_quote_fails_closed(self):
        def bad(instruction, payload):
            data = model(instruction, payload); data['papers'][0]['evidence_quote'] = 'This unsupported quotation cannot be found in the original source.'; return data
        self.assertEqual(self.execute(call=bad), 'model_error')

    def test_unverified_institution_becomes_unknown(self):
        def altered(instruction, payload):
            data = model(instruction, payload)
            if 'papers' in data: data['papers'][0]['institution'] = 'Fabricated University'
            return data
        self.assertEqual(self.execute(call=altered), 'generated')
        self.assertEqual(self.export()['digests'][0]['papers'][0]['institution'], 'Unknown')

    def test_all_excluded_is_complete_empty_batch(self):
        def excluded(instruction, payload):
            return {'papers': [{'arxiv_id': p['arxiv_id'],'include':False,'reason':'无实际系统机制',
                     'summary':'','systems_problem':'','mapping':'','institution':'Unknown','code_url':None,'tags':[],
                     'evidence_quote':'','limitations':''} for p in payload]}
        self.assertEqual(self.execute(call=excluded), 'generated')
        self.assertEqual(self.export()['digests'][0]['papers'], [])

    def test_model_cannot_add_fields(self):
        def bad(instruction, payload):
            data=model(instruction,payload);data['papers'][0]['notes']='TEST PRIVATE';return data
        self.assertEqual(self.execute(call=bad), 'model_error')

    def test_budget_checked_before_request(self):
        c = {'calls': MAX_CALLS_DAY}
        with patch('update_digest.build_opener', side_effect=AssertionError('network')):
            with self.assertRaisesRegex(PipelineError, 'waiting_quota'):
                Gemini('TEST ONLY', c, self.root/'data/cache.json')('test', {})

    def test_private_status_fields_rejected(self):
        self.execute(); data=self.export(); data['pipeline']['auth']='TEST PRIVATE'
        with self.assertRaises(ValueError): validate(data)

    def test_cursor_must_match_digests(self):
        self.execute(); data=self.export(); data['pipeline']['latest_generated_date']='2026-10-08'
        with self.assertRaises(ValueError): validate(data)


if __name__ == '__main__': unittest.main()
