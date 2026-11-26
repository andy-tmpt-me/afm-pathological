import re
from datetime import datetime, timezone

import pytest

from afm_pathological.catalog import cases

NOW = datetime(2026, 11, 25, 12, 0, 45, tzinfo=timezone.utc)
ERROR_SLOT = NOW.replace(second=10)
CHROME_120 = 'Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
HEADERS = {'accept-language': 'en-US', 'sec-fetch-mode': 'navigate'}


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def test_section_links(fetch):
    """The section page links to the three cases that are not own sources."""
    response = fetch('/bouncer/')
    assert re.findall(r'<a href="([^"]*)"', response.body.decode()) == [
        '/bouncer/stale-browser', '/bouncer/needs-headers', '/bouncer/challenge']
    tags = {c.name: c.tags for c in cases() if c.family == 'bouncer'}
    assert tags['stale-browser'] == ('production only',) and tags['rate-limit'] == ('own source', 'local only')


def test_stale_browser(fetch):
    """403 for the fixed Chrome 120 User-Agent, an article for each other request."""
    refused = fetch('/bouncer/stale-browser', headers={'user-agent': CHROME_120})
    assert refused.status == 403 and 'etag' not in refused.headers
    assert fetch('/bouncer/stale-browser', method='HEAD', headers={'user-agent': CHROME_120}).status == 403
    for headers in ({}, {'user-agent': 'Mozilla/5.0 Chrome/131.0.0.0'}):
        ok = fetch('/bouncer/stale-browser', headers=headers)
        assert ok.status == 200 and _words(ok) >= 250


def test_needs_headers(fetch):
    """403 when Accept-Language or Sec-Fetch-Mode is missing."""
    assert fetch('/bouncer/needs-headers').status == 403
    for missing in HEADERS:
        assert fetch('/bouncer/needs-headers', headers={k: v for k, v in HEADERS.items() if k != missing}).status == 403
    ok = fetch('/bouncer/needs-headers', headers=HEADERS)
    assert ok.status == 200 and _words(ok) >= 250


def test_rate_section(fetch):
    """The source page links to 30 pages and is 200 in both slots."""
    for now in (ERROR_SLOT, NOW):
        response = fetch('/bouncer/rate/', now=now)
        assert response.status == 200
        assert re.findall(r'<a href="([^"]*)"', response.body.decode()) == [f'/bouncer/rate/{n}' for n in range(1, 31)]


@pytest.mark.parametrize('n', [1, 17, 30])
def test_rate_pages(fetch, n):
    """429 with Retry-After in the error slot, an article in the ok slot."""
    limited = fetch(f'/bouncer/rate/{n}', now=ERROR_SLOT)
    assert limited.status == 429 and limited.headers['retry-after'] == '30' and 'etag' not in limited.headers
    ok = fetch(f'/bouncer/rate/{n}', now=NOW)
    assert ok.status == 200 and _words(ok) >= 250
    assert ok.body != fetch(f'/bouncer/rate/{n % 30 + 1}', now=NOW).body


@pytest.mark.parametrize('path', ['/bouncer/rate/0', '/bouncer/rate/31', '/bouncer/rate/x'])
def test_rate_unknown(fetch, path):
    """Only 1 to 30 exist."""
    assert fetch(path, now=NOW).status == 404


def test_challenge(fetch):
    """200 text/html with the challenge title and cf-chl."""
    response = fetch('/bouncer/challenge')
    body = response.body.decode()
    assert response.status == 200 and response.headers['content-type'].startswith('text/html')
    assert '<title>Just a moment...</title>' in body and 'cf-chl' in body
