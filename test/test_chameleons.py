import re
from datetime import datetime, timedelta, timezone

from afm_pathological.clock import EPOCH, http_date

NOW = datetime(2026, 11, 25, 12, 0, 45, 123456, tzinfo=timezone.utc)
LATER = NOW + timedelta(microseconds=1)


def _on(n: int) -> dict[str, str]:
    """The header that sets the day number to n."""
    return {'x-pathological-date': (EPOCH + timedelta(days=n)).isoformat()}


def _links(response) -> list[str]:
    """The href of each <a> element of a response body."""
    return re.findall(r'<a href="([^"]*)"', response.body.decode())


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def test_section_links(fetch):
    """The section page links to the case pages, not to own-source or follow-up pages."""
    response = fetch('/chameleons/')
    assert response.status == 200 and _words(response) >= 250
    assert _links(response) == [
        '/chameleons/honest-edit', '/chameleons/silent-edit', '/chameleons/restless-header',
        '/chameleons/restless-markup', '/chameleons/visible-timestamp', '/chameleons/rotating-sidebar',
        '/chameleons/counter', '/chameleons/no-validators', '/chameleons/head-refused', '/chameleons/head-differs',
        '/chameleons/cdn-headers', '/chameleons/new-link/hub', '/chameleons/removed-404', '/chameleons/removed-410',
        '/chameleons/moved-old', '/chameleons/outage']


def test_honest_edit(fetch):
    """The text, ETag and Last-Modified change with N; a conditional GET answers 304 for the same day."""
    first, second = fetch('/chameleons/honest-edit', headers=_on(5)), fetch('/chameleons/honest-edit', headers=_on(6))
    assert first.body != second.body and first.headers['etag'] != second.headers['etag']
    assert first.headers['last-modified'] == 'Tue, 06 Jan 2026 00:00:00 GMT'
    assert _words(first) >= 250
    again = fetch('/chameleons/honest-edit', headers={**_on(5), 'if-none-match': first.headers['etag']})
    assert again.status == 304
    assert fetch('/chameleons/honest-edit', headers={**_on(6), 'if-none-match': first.headers['etag']}).status == 200


def test_silent_edit(fetch):
    """The text changes with N; ETag and Last-Modified never change; any conditional GET answers 304."""
    first, second = fetch('/chameleons/silent-edit', headers=_on(5)), fetch('/chameleons/silent-edit', headers=_on(6))
    assert first.body != second.body and _words(first) >= 250
    for response in (first, second):
        assert response.headers['etag'] == '"v1"'
        assert response.headers['last-modified'] == http_date(EPOCH)
    for conditional in ({'if-none-match': '"other"'}, {'if-modified-since': 'Thu, 01 Jan 2026 00:00:00 GMT'},
                        {'if-modified-since': 'Mon, 01 Jan 2024 00:00:00 GMT'}):
        response = fetch('/chameleons/silent-edit', headers={**_on(6), **conditional})
        assert response.status == 304 and response.body == b'' and response.headers['etag'] == '"v1"'


def test_restless_header(fetch):
    """The text is constant; Last-Modified is the time of the request; no ETag; never 304."""
    first = fetch('/chameleons/restless-header')
    second = fetch('/chameleons/restless-header', now=NOW + timedelta(days=1))
    assert first.body == second.body and 'etag' not in first.headers
    assert first.headers['last-modified'] == 'Wed, 25 Nov 2026 12:00:45 GMT'
    assert second.headers['last-modified'] == 'Thu, 26 Nov 2026 12:00:45 GMT'
    conditional = {'if-modified-since': first.headers['last-modified']}
    assert fetch('/chameleons/restless-header', headers=conditional).status == 200


def test_restless_markup(fetch):
    """The text is constant; a comment and a data-token attribute of <body> change with each request."""
    first, second = fetch('/chameleons/restless-markup', now=NOW), fetch('/chameleons/restless-markup', now=LATER)
    strip = lambda r: re.sub(r'<!--.*?-->|data-token="[^"]*"', '', r.body.decode())  # noqa: E731
    assert first.body != second.body and strip(first) == strip(second)
    token = re.search(r'<body data-token="([0-9a-f]+)">', first.body.decode()).group(1)
    assert f'<!-- {token} -->' in first.body.decode()
    assert first.headers['etag'] != second.headers['etag'] and _words(first) >= 250


def test_visible_timestamp_and_counter(fetch):
    """One paragraph has the time of the request; counter has the Unix time."""
    stamp = fetch('/chameleons/visible-timestamp')
    assert '<p>Generated at 2026-11-25T12:00:45' in stamp.body.decode() and _words(stamp) >= 250
    assert stamp.body != fetch('/chameleons/visible-timestamp', now=NOW + timedelta(seconds=1)).body
    counter = fetch('/chameleons/counter')
    assert f'<p>Viewed {int(NOW.timestamp())} times</p>' in counter.body.decode()
    assert counter.body != fetch('/chameleons/counter', now=NOW + timedelta(seconds=1)).body


def test_rotating_sidebar(fetch):
    """The article is constant; an <aside> lists 3 of 10 titles in plain text, selected by the request time."""
    seen = set()
    bodies = []
    for second in range(20):
        body = fetch('/chameleons/rotating-sidebar', now=NOW + timedelta(seconds=second)).body.decode()
        aside = re.search(r'<aside>(.*?)</aside>', body, re.S).group(1)
        titles = re.findall(r'<li>(.*?)</li>', aside)
        assert len(titles) == 3 and len(set(titles)) == 3 and '<a' not in aside
        seen.update(titles)
        bodies.append(re.sub(r'<aside>.*?</aside>', '', body, flags=re.S))
    assert len(seen) > 3 and len(set(bodies)) == 1


def test_no_validators(fetch):
    """No ETag, no Last-Modified, never 304."""
    response = fetch('/chameleons/no-validators', headers={'if-modified-since': 'Fri, 01 Jan 2100 00:00:00 GMT'})
    assert response.status == 200 and 'etag' not in response.headers and 'last-modified' not in response.headers


def test_head_refused(fetch):
    """GET answers 200 with an ETag; HEAD answers 403; head-405 answers 405 to HEAD only."""
    assert fetch('/chameleons/head-refused').headers['etag']
    assert fetch('/chameleons/head-refused', method='HEAD').status == 403
    assert fetch('/chameleons/head-405').status == 200
    assert fetch('/chameleons/head-405', method='HEAD').status == 405


def test_head_differs(fetch):
    """The ETag of a HEAD is "head" and the ETag of a GET is "get"."""
    assert fetch('/chameleons/head-differs').headers['etag'] == '"get"'
    head = fetch('/chameleons/head-differs', method='HEAD')
    assert head.status == 200 and head.headers['etag'] == '"head"'


def test_cdn_headers(fetch):
    """Date is the time of the request, Age is 600, Last-Modified is constant."""
    first, second = fetch('/chameleons/cdn-headers'), fetch('/chameleons/cdn-headers', now=NOW + timedelta(days=1))
    assert first.headers['date'] == 'Wed, 25 Nov 2026 12:00:45 GMT' and first.headers['age'] == '600'
    assert second.headers['date'] == 'Thu, 26 Nov 2026 12:00:45 GMT'
    assert first.headers['last-modified'] == second.headers['last-modified'] == http_date(EPOCH)


def test_new_link(fetch):
    """The hub links to the pages of the date and the six before it; a later date is 404."""
    hub = fetch('/chameleons/new-link/hub')
    assert _links(hub) == [f'/chameleons/new-link/2026-11-{day}' for day in range(25, 18, -1)]
    assert _words(hub) >= 250
    assert _words(fetch('/chameleons/new-link/2026-11-25')) >= 250
    assert fetch('/chameleons/new-link/2026-11-19').body != fetch('/chameleons/new-link/2026-11-20').body
    assert fetch('/chameleons/new-link/2026-11-26').status == 404
    assert fetch('/chameleons/new-link/2026-11-26', headers={'x-pathological-date': '2026-11-26'}).status == 200
    assert fetch('/chameleons/new-link/yesterday').status == 404


def test_removed_pages(fetch):
    """200 when N mod 14 is below 7, else 404 for removed-404 and 410 for removed-410."""
    for n, present in ((0, True), (6, True), (7, False), (13, False), (14, True), (21, False)):
        assert (fetch('/chameleons/removed-404', headers=_on(n)).status == 200) is present, n
        assert fetch('/chameleons/removed-404', headers=_on(n)).status == (200 if present else 404)
        assert fetch('/chameleons/removed-410', headers=_on(n)).status == (200 if present else 410)
    assert _words(fetch('/chameleons/removed-410', headers=_on(0))) >= 250


def test_moved_pages(fetch):
    """moved-old is 200 when N mod 14 is below 7, else 301 to moved-new; moved-new has a canonical on itself."""
    assert fetch('/chameleons/moved-old', headers=_on(6)).status == 200
    moved = fetch('/chameleons/moved-old', headers=_on(7))
    assert moved.status == 301 and moved.headers['location'] == '/chameleons/moved-new'
    for n in (0, 7):
        new = fetch('/chameleons/moved-new', headers=_on(n))
        assert new.status == 200
        url = 'https://breadcrumbs.pathological.answersfrom.me/chameleons/moved-new'
        assert f'<link rel="canonical" href="{url}">' in new.body.decode()


def test_outage(fetch):
    """503 when N is odd, 200 when even."""
    assert fetch('/chameleons/outage', headers=_on(4)).status == 200
    assert fetch('/chameleons/outage', headers=_on(5)).status == 503


def test_outage_section(fetch):
    """The source page answers 503 on an odd day and links to three articles; the articles are always 200."""
    even = fetch('/chameleons/outage-section/', headers=_on(4))
    odd = fetch('/chameleons/outage-section/', headers=_on(5))
    assert even.status == 200 and odd.status == 503
    assert _links(even) == [f'/chameleons/outage-section/{i}' for i in (1, 2, 3)]
    for n in (4, 5):
        for i in (1, 2, 3):
            assert _words(fetch(f'/chameleons/outage-section/{i}', headers=_on(n))) >= 250
    assert fetch('/chameleons/outage-section/4').status == 404


def test_moved_new_canonical_is_escaped(fetch):
    """A host with a quote stays inside the href of the canonical link."""
    body = fetch('/chameleons/moved-new', host='breadcrumbs.a"b&c').body.decode()
    assert '<link rel="canonical" href="https://breadcrumbs.a&quot;b&amp;c/chameleons/moved-new">' in body
