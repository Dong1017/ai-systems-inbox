"""Assemble public analyses; importing history never completes an official batch."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from validate_site import validate, require, keys, text

ROOT = Path(__file__).resolve().parents[1]
HISTORY_REPORT = {'report_date', 'reported_listing_date', 'title', 'signal', 'mind_model', 'papers'}
HISTORY_PAPER = {'id', 'title', 'status', 'tags', 'priority', 'analysis', 'problem', 'mapping'}


def read_json(path: Path, limit: int = 1_000_000) -> object:
    require(not path.is_symlink(), 'public source must not be a symlink')
    require(path.stat().st_size <= limit, 'public source file too large')
    return json.loads(path.read_text(encoding='utf-8'))


def day(value: object) -> str:
    text(value, 'history date')
    require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)), 'history date format')
    dt.date.fromisoformat(value)
    return value


def history_digests(path: Path) -> list[dict]:
    """Expand an explicitly reviewed public extract, never a private history export.

    Dates identify old report headings. Reported listing dates are retained only
    as unverified provenance; neither is used to advance completed-batch state.
    A direct date file takes precedence in build(), without editing either input.
    """
    require(not path.parent.is_symlink(), 'history directory must not be a symlink')
    if not path.exists():
        require(not path.is_symlink(), 'dangling history symlink')
        return []
    data = read_json(path)
    keys(data, {'schema_version', 'kind', 'imported_at', 'reports'}, 'public history')
    require(type(data['schema_version']) is int and data['schema_version'] == 1, 'history schema')
    require(data['kind'] == 'public_daily_analysis_archive', 'not a public daily archive')
    text(data['imported_at'], 'import time')
    require('T' in data['imported_at'], 'import time must contain time')
    imported = dt.datetime.fromisoformat(data['imported_at'].replace('Z', '+00:00'))
    require(imported.tzinfo is not None, 'import time must contain timezone')
    require(isinstance(data['reports'], list), 'history reports must be a list')
    digests, seen = [], set()
    for report in data['reports']:
        keys(report, HISTORY_REPORT, 'history report')
        date = day(report['report_date'])
        require(date not in seen, 'duplicate history report date')
        seen.add(date)
        reported = report['reported_listing_date']
        if reported is not None:
            day(reported)
            require(reported <= date, 'reported listing after original report')
        for field in ('title', 'signal', 'mind_model'):
            text(report[field], 'history ' + field)
        require(isinstance(report['papers'], list) and bool(report['papers']), 'empty history report')
        papers = []
        for item in report['papers']:
            require(isinstance(item, dict), 'history paper must be an object')
            require(set(item) in (HISTORY_PAPER, HISTORY_PAPER | {'reported_version'}),
                    'unexpected or missing public history paper fields')
            for field in ('analysis', 'problem', 'mapping'):
                text(item[field], 'history ' + field)
            version = item.get('reported_version', '')
            text(version, 'reported version', True)
            require(not version or bool(re.fullmatch(r'v[1-9]\d*', version)), 'reported version')
            papers.append({
                'arxiv_id': item['id'], 'version': '', 'status': item['status'],
                'title': item['title'], 'summary': item['analysis'], 'tags': item['tags'],
                'read_now': item['priority'], 'institution': 'Unknown', 'code_url': None,
                'systems_problem': item['problem'], 'mapping': item['mapping'],
                'evidence': (
                    f'转存自 {date} 历史论文简报的公开技术分析；不是完整逐字会话。'
                    '标题、编号、new/cross-list/revised 状态、机制与数值未在此次迁移中重新核验；'
                    '机构、代码和当前版本不作已核验断言。未独立复现；工程映射是历史分析推断。'
                    + (f'原稿引用 {version}，仅保留版本引用记录。' if version else '')
                ),
                'sources': [{'label': '历史引用的 arXiv 入口（本次未复核）',
                             'url': 'https://arxiv.org/abs/' + str(item['id'])}],
            })
        note = (
            '历史分析转存 · 未重新核验。归档日期沿用原简报标题日期 ' + date + '，'
            '不把它当作已核验的 arXiv listing date。'
            + ('原稿标注的 listing date 为 ' + reported + '，同样未在本次复核。' if reported else '')
            + f'本页保留 {len(papers)} 条可按历史编号定位的分析，条目数不是完整官方批次总数。'
            '状态和性能陈述仅作历史记录；不推进新论文采集或完整批次进度。\n\n'
        )
        digest = {'listing_date': date, 'published_at': data['imported_at'],
                  'source_count': len(papers), 'complete': False,
                  'signal_title': report['title'], 'signal': note + report['signal'],
                  'mind_model': report['mind_model'], 'papers': papers}
        validate({'schema_version': 1, 'generation_status': 'configured', 'digests': [digest]})
        digests.append(digest)
    return digests


def build(source: Path) -> dict:
    direct = []
    for path in sorted(source.glob('*.json')):
        require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}\.json', path.name)), 'unexpected digest filename')
        digest = read_json(path)
        require(isinstance(digest, dict), 'digest must be an object')
        require(digest.get('listing_date') == path.stem, 'filename/listing date mismatch')
        require(type(digest.get('complete')) is bool, 'direct digest requires complete: true/false')
        validate({'schema_version': 1, 'generation_status': 'configured', 'digests': [digest]})
        direct.append(digest)
    direct.sort(key=lambda d: d['listing_date'], reverse=True)
    history_dir = source / 'history'
    require(not history_dir.is_symlink(), 'history directory must not be a symlink')
    by_date = {}
    for path in sorted(history_dir.glob('*.json')):
        for digest in history_digests(path):
            require(digest['listing_date'] not in by_date, 'duplicate history date across files')
            by_date[digest['listing_date']] = digest
    # Explicit date files remain authoritative, including an existing incomplete one.
    by_date.update({d['listing_date']: d for d in direct})
    digests = sorted(by_date.values(), key=lambda d: d['listing_date'], reverse=True)
    output = {'schema_version': 1, 'generation_status': 'configured', 'digests': digests}
    if digests:
        latest = direct[0] if direct else digests[0]
        complete = max((d['listing_date'] for d in direct if d['complete']), default=None)
        output['pipeline'] = {
            'checked_at': latest['published_at'],
            'state': 'generated' if latest['complete'] else 'source_incomplete',
            'message': ('ChatGPT 分析已提交；Actions 仅负责校验与发布。'
                        if latest['complete'] else
                        '历史/会话分析可阅读，尚未完成全批核验；不推进完整批次进度。'),
            'source_listing_date': latest['listing_date'],
            'source_count': latest['source_count'],
            'section_counts': None,
            'latest_generated_date': complete,
        }
    validate(output)
    return output


if __name__ == '__main__':
    output = build(ROOT / 'data' / 'digests')
    path = ROOT / 'site' / 'digests.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    print(f"Assembled {len(output['digests'])} readable analyses; no model API used.")
