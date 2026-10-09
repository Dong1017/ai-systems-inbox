"""Validate the public export. This does not verify scientific claims."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TOP = {'schema_version', 'generation_status', 'digests'}
DIGEST = {'listing_date', 'published_at', 'source_count', 'signal_title',
          'signal', 'mind_model', 'papers'}
PAPER = {'arxiv_id', 'version', 'status', 'title', 'summary', 'tags',
         'read_now', 'institution', 'code_url', 'systems_problem',
         'mapping', 'evidence', 'sources'}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def keys(value: object, expected: set[str], where: str) -> None:
    require(isinstance(value, dict), f'{where}: expected an object')
    require(set(value) == expected, f'{where}: unexpected or missing fields')


def text(value: object, where: str, allow_empty: bool = False) -> None:
    require(isinstance(value, str), f'{where}: expected text')
    require(allow_empty or bool(value.strip()), f'{where}: empty text')
    require(len(value) <= 20000, f'{where}: text too long')


def https(value: object, where: str) -> None:
    text(value, where)
    url = urlsplit(value)
    require(url.scheme == 'https' and bool(url.hostname)
            and not url.username and not url.password,
            f'{where}: expected an HTTPS URL without credentials')
    require(not any(c.isspace() for c in value), f'{where}: whitespace in URL')


def validate_pipeline(value: object) -> None:
    keys(value, {'checked_at', 'state', 'message', 'source_listing_date', 'source_count',
                 'section_counts', 'latest_generated_date'}, 'pipeline')
    text(value['checked_at'], 'pipeline timestamp')
    at = dt.datetime.fromisoformat(value['checked_at'].replace('Z', '+00:00'))
    require(at.tzinfo is not None, 'pipeline timestamp must contain timezone')
    states = {'initialized', 'waiting_model', 'generated', 'no_new', 'source_dates_disagree',
              'source_stale', 'source_regression', 'source_incomplete', 'source_error',
              'model_error', 'waiting_quota', 'internal_error'}
    require(value['state'] in states, 'unknown pipeline state')
    text(value['message'], 'pipeline message')
    require(len(value['message']) <= 240, 'pipeline message too long')
    for field in ('source_listing_date', 'latest_generated_date'):
        if value[field] is not None:
            require(isinstance(value[field], str) and bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value[field])), 'pipeline date')
            dt.date.fromisoformat(value[field])
    count = value['source_count']
    require(count is None or (type(count) is int and 0 <= count <= 2000), 'pipeline count')
    if value['section_counts'] is not None:
        keys(value['section_counts'], {'new', 'cross-list', 'revised'}, 'section_counts')
        require(all(type(v) is int and v >= 0 for v in value['section_counts'].values()), 'section count')
        require(sum(value['section_counts'].values()) == count, 'section sum')
    if value['state'] in {'generated', 'no_new'}:
        require(value['source_listing_date'] is not None and value['source_listing_date'] == value['latest_generated_date'], 'state date mismatch')


def validate(data: object) -> None:
    require(isinstance(data, dict), 'export must be an object')
    require(set(data) in (TOP, TOP | {'pipeline'}), 'export fields')
    if 'pipeline' in data:
        validate_pipeline(data['pipeline'])
    require(type(data['schema_version']) is int and data['schema_version'] == 1,
            'unsupported schema')
    require(data['generation_status'] in {'not_configured', 'configured'},
            'unknown generation status')
    require(isinstance(data['digests'], list), 'digests must be a list')
    dates: set[str] = set()
    completed_dates: set[str] = set()
    for digest in data['digests']:
        require(isinstance(digest, dict), 'digest must be an object')
        require(set(digest) in (DIGEST, DIGEST | {'complete'}), 'unexpected or missing digest fields')
        require(type(digest.get('complete', True)) is bool, 'complete must be boolean')
        date = digest['listing_date']
        text(date, 'listing_date')
        require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', date)), 'date format')
        dt.date.fromisoformat(date)
        require(date not in dates, 'duplicate listing date')
        dates.add(date)
        # Conversation imports may be readable without proving complete source coverage.
        if digest.get('complete', True):
            completed_dates.add(date)
        timestamp = digest['published_at']
        text(timestamp, 'published_at')
        require('T' in timestamp, 'timestamp must contain time')
        parsed = dt.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None, 'timestamp must contain timezone')
        require(parsed.date() >= dt.date.fromisoformat(date), 'publication before listing')
        require(type(digest['source_count']) is int and digest['source_count'] >= 0,
                'invalid source count')
        for field in ('signal_title', 'signal', 'mind_model'):
            text(digest[field], field)
        require(isinstance(digest['papers'], list), 'papers must be a list')
        require(len(digest['papers']) <= digest['source_count'], 'count mismatch')
        ids: set[str] = set()
        for paper in digest['papers']:
            keys(paper, PAPER, 'paper')
            ident = paper['arxiv_id']
            text(ident, 'arxiv_id')
            require(bool(re.fullmatch(r'\d{4}\.\d{4,5}', ident)), 'invalid arxiv id')
            require(ident not in ids, 'duplicate paper in batch')
            ids.add(ident)
            text(paper['version'], 'version', True)
            require(not paper['version'] or bool(re.fullmatch(r'v[1-9]\d*', paper['version'])),
                    'invalid version')
            require(paper['status'] in {'new', 'cross-list', 'revised'}, 'invalid status')
            require(type(paper['read_now']) is bool, 'read_now must be boolean')
            for field in ('title', 'summary', 'institution', 'systems_problem', 'mapping', 'evidence'):
                text(paper[field], field)
            require(isinstance(paper['tags'], list), 'tags must be a list')
            for value in paper['tags']:
                text(value, 'tag')
            require(len(set(paper['tags'])) == len(paper['tags']), 'duplicate tags')
            require(paper['code_url'] is None or isinstance(paper['code_url'], str),
                    'code_url must be null or URL')
            if paper['code_url'] is not None:
                https(paper['code_url'], 'code_url')
            require(isinstance(paper['sources'], list) and bool(paper['sources']),
                    'at least one evidence source required')
            own_source = False
            for source in paper['sources']:
                keys(source, {'label', 'url'}, 'source')
                text(source['label'], 'source label')
                https(source['url'], 'source url')
                u = urlsplit(source['url'])
                expected = re.escape(ident) + r'(?:v[1-9]\d*)?'
                if (u.hostname == 'arxiv.org' and
                        re.fullmatch(r'/(?:abs|html|pdf)/' + expected + r'(?:\.pdf)?', u.path)):
                    own_source = True
            require(own_source, 'matching arXiv source required')

    if 'pipeline' in data:
        require(data['pipeline']['latest_generated_date'] == max(completed_dates, default=None), 'pipeline cursor does not match complete digests')


def validate_site(site: Path) -> None:
    # Never upload the repository root, private database, or history bundle.
    expected = {'index.html', 'digests.json'}
    actual: set[str] = set()
    for entry in site.rglob('*'):
        require(not entry.is_symlink(), 'symlinks not allowed in public export')
        if entry.is_file():
            actual.add(entry.relative_to(site).as_posix())
    require(actual == expected, f'public export file allowlist mismatch: {actual}')
    validate(json.loads((site / 'digests.json').read_text(encoding='utf-8')))


if __name__ == '__main__':
    validate_site(ROOT / 'site')
    print('Public export schema and file allowlist passed; factual review remains separate.')
