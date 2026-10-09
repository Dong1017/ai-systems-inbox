"""Assemble committed public digests; no network access or model invocation."""
from __future__ import annotations

import json
import re
from pathlib import Path

from validate_site import validate, require

ROOT = Path(__file__).resolve().parents[1]


def build(source: Path) -> dict:
    digests = []
    for path in sorted(source.glob('*.json')):
        require(not path.is_symlink(), 'digest source must not be a symlink')
        require(bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}\.json', path.name)), 'unexpected digest filename')
        require(path.stat().st_size <= 1_000_000, 'digest file too large')
        digest = json.loads(path.read_text(encoding='utf-8'))
        require(isinstance(digest, dict), 'digest must be an object')
        require(digest.get('listing_date') == path.stem, 'filename/listing date mismatch')
        require(type(digest.get('complete')) is bool, 'direct digest requires complete: true/false')
        validate({'schema_version': 1, 'generation_status': 'configured', 'digests': [digest]})
        digests.append(digest)
    digests.sort(key=lambda d: d['listing_date'], reverse=True)
    output = {'schema_version': 1, 'generation_status': 'configured', 'digests': digests}
    if digests:
        latest = digests[0]
        complete = max((d['listing_date'] for d in digests if d['complete']), default=None)
        output['pipeline'] = {
            'checked_at': latest['published_at'],
            'state': 'generated' if latest['complete'] else 'source_incomplete',
            'message': ('ChatGPT 分析已提交；Actions 仅负责校验与发布。'
                        if latest['complete'] else
                        '会话分析已转存，尚未完成全批核验；不推进完整批次进度。'),
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
    print(f"Assembled {len(output['digests'])} committed digests; no model API used.")
