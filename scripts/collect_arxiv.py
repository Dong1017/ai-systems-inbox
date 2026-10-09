"""Read a complete official cs.DC batch. Errors never become an empty digest."""
from __future__ import annotations

import hashlib
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from bs4 import BeautifulSoup

NEW_URL = 'https://arxiv.org/list/cs.DC/new?show=2000'
RECENT_URL = 'https://arxiv.org/list/cs.DC/recent?show=2000'
ID = r'\d{4}\.\d{4,5}'
ABS = re.compile(r'/abs/(' + ID + r')(v[1-9]\d*)?(?:$|[?#])')


class PipelineError(ValueError):
    """A safe error code, never an upstream body, key, or arbitrary error text."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def get_html(url: str) -> str:
    u = urlsplit(url)
    if (u.scheme != 'https' or u.netloc != 'arxiv.org' or
            not (u.path.startswith('/list/cs.DC/') or re.fullmatch(r'/(abs|html)/' + ID + r'(v[1-9]\d*)?', u.path))):
        raise PipelineError('source_url_rejected')
    for attempt in range(3):
        # One connection at a time; leave at least three seconds between requests.
        time.sleep(3)
        try:
            req = Request(url, headers={'User-Agent': 'AI-Systems-Inbox/0.2 (https://github.com/Dong1017/ai-systems-inbox)',
                                        'Cache-Control': 'no-cache'})
            with build_opener(NoRedirect()).open(req, timeout=25) as response:
                if response.headers.get_content_type() != 'text/html':
                    raise PipelineError('source_not_html')
                body = response.read(12_000_001)
                if len(body) > 12_000_000:
                    raise PipelineError('source_too_large')
                return body.decode('utf-8')
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise PipelineError('source_http_error') from None
        except (URLError, TimeoutError, OSError, UnicodeError):
            if attempt == 2:
                raise PipelineError('source_unavailable') from None
        time.sleep(3 * (attempt + 1))
    raise PipelineError('source_unavailable')


def label(value, name):
    return re.sub(r'^\s*' + name + r'\s*:\s*', '', value, flags=re.I).strip()


def parse_listing(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    date = re.search(r'Showing new listings for\s+([A-Za-z]+,?\s+\d{1,2}\s+[A-Za-z]+\s+\d{4})', text)
    total = re.search(r'Total of\s+([\d,]+)\s+entr', text)
    if not date or not total:
        raise PipelineError('source_structure_changed')
    try:
        day = datetime.strptime(date[1].replace(',', ''), '%A %d %B %Y').date().isoformat()
    except ValueError:
        raise PipelineError('source_date_invalid') from None
    expected = int(total[1].replace(',', ''))
    if expected > 2000:
        raise PipelineError('source_pagination_required')
    mode, records, counts = None, [], {}
    for node in soup.find_all(['h3', 'dt']):
        if node.name == 'h3':
            heading = node.get_text(' ', strip=True).lower()
            if 'new submission' in heading:
                mode = 'new'
            elif 'cross' in heading and ('list' in heading or 'submission' in heading):
                mode = 'cross-list'
            elif 'replacement' in heading or 'revised' in heading:
                mode = 'revised'
            else:
                continue
            count = re.search(r'showing\s+([\d,]+)\s+of\s+([\d,]+)', heading)
            if not count or count[1] != count[2] or mode in counts:
                raise PipelineError('source_incomplete')
            counts[mode] = int(count[2].replace(',', ''))
            continue
        link = next((a for a in node.find_all('a', href=True) if ABS.search(a['href'])), None)
        if link is None:
            continue
        dd = node.find_next_sibling()
        if mode is None or dd is None or dd.name != 'dd':
            raise PipelineError('source_incomplete')
        ident = ABS.search(link['href'])
        title = dd.select_one('.list-title')
        if not title:
            raise PipelineError('source_incomplete')
        abstract = dd.select_one('.list-abstract') or dd.select_one('p.mathjax')
        authors = dd.select_one('.list-authors')
        subjects = dd.select_one('.list-subjects')
        version = ident[2] or ''
        if not version:
            found = re.search(re.escape(ident[1]) + r'(v[1-9]\d*)\b', node.get_text(' ', strip=True))
            version = found[1] if found else ''
        records.append({'arxiv_id': ident[1], 'version': version, 'status': mode,
                        'title': label(title.get_text(' ', strip=True), 'Title'),
                        'abstract': label(abstract.get_text(' ', strip=True), 'Abstract') if abstract else '',
                        'authors': [a.get_text(' ', strip=True) for a in authors.select('a')] if authors else [],
                        'categories': re.findall(r'\(([a-z-]+\.[A-Za-z]+)\)', subjects.get_text()) if subjects else []})
    if len(records) != expected or sum(counts.values()) != expected:
        raise PipelineError('source_incomplete')
    for status, count in counts.items():
        if sum(p['status'] == status for p in records) != count:
            raise PipelineError('source_incomplete')
    # Explicitly zero sections may be omitted. Never infer a missing positive section.
    counts = {s: counts.get(s, 0) for s in ('new', 'cross-list', 'revised')}
    unique = {}
    for p in records:
        old = unique.get(p['arxiv_id'])
        if old and (not old['version'] or not p['version']):
            raise PipelineError('source_ambiguous_duplicate')
        if old is None or int(p['version'][1:] or '0') > int(old['version'][1:] or '0'):
            unique[p['arxiv_id']] = p
    return {'listing_date': day, 'source_count': expected, 'counts': counts,
            'papers': list(unique.values()), 'source_url': NEW_URL,
            'source_sha256': hashlib.sha256(html.encode()).hexdigest()}


def check_freshness(batch, recent_html, now=None):
    now = now or datetime.now(timezone.utc)
    text = BeautifulSoup(recent_html, 'html.parser').get_text(' ', strip=True)
    date = re.search(r'\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\b', text)
    if not date:
        raise PipelineError('recent_structure_changed')
    recent = datetime.strptime(date[0], '%a, %d %b %Y').date().isoformat()
    if recent != batch['listing_date']:
        raise PipelineError('source_dates_disagree')
    age = (now.date() - datetime.fromisoformat(recent).date()).days
    if not 0 <= age <= 7:
        raise PipelineError('source_stale')


def enrich(paper: dict, fetch=get_html) -> dict:
    """Bound the evidence sent to the model. Do not crawl arbitrary author links."""
    p = dict(paper)
    url = 'https://arxiv.org/abs/' + p['arxiv_id'] + p['version']
    p['sources'] = [{'label': 'arXiv metadata / abstract', 'url': url}]
    p['code_links'] = []
    p['evidence_scope'] = 'abstract'
    if not p['abstract']:
        soup = BeautifulSoup(fetch(url), 'html.parser')
        block = soup.select_one('blockquote.abstract')
        if not block:
            raise PipelineError('abstract_unavailable')
        p['abstract'] = label(block.get_text(' ', strip=True), 'Abstract')
    p['source_text'] = p['abstract']
    # Avoid reading a newer paper revision than the current batch.
    if p['version']:
        article_url = 'https://arxiv.org/html/' + p['arxiv_id'] + p['version']
        try:
            article = BeautifulSoup(fetch(article_url), 'html.parser').select_one('article')
            if article is not None:
                for n in article.select('.ltx_bibliography, script, style, figure, table'):
                    n.decompose()
                p['source_text'] += '\n' + article.get_text(' ', strip=True)[:16000]
                p['evidence_scope'] = 'abstract_and_text_excerpt_no_figures'
                p['sources'].append({'label': 'arXiv HTML text excerpt (figures not checked)', 'url': article_url})
                p['code_links'] = sorted({a['href'] for a in article.select('a[href]')
                    if re.match(r'https://(?:github\.com|gitlab\.com)/[\w.-]+/[\w.-]+/?$', a['href'])})[:10]
        except PipelineError:
            pass  # Full text is optional; the output explicitly labels abstract-only evidence.
    return p
