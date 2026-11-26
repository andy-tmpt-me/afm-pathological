import re
from datetime import datetime, timezone

from afm_pathological.catalog import Case, cases, find, section_case
from afm_pathological.content import article
from afm_pathological.model import Request

ARTICLES = ['starter', 'hydration', 'scoring', 'steam', 'crumb']


def _links(response) -> list[str]:
    """The href of each <a> element of a response body."""
    return re.findall(r'<a href="([^"]*)"', response.body.decode())


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def test_articles_section(fetch):
    """/articles/ is an article of 250 or more words that links to the five articles after its text."""
    response = fetch('/articles/')
    assert response.status == 200
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert _links(response) == [f'/articles/{name}' for name in ARTICLES]
    assert _words(response) >= 250
    body = response.body.decode()
    assert body.rindex('</p>') < body.index('<a ')


def test_articles(fetch):
    """Each article and /articles/unlisted is a constant article; only crumb links, to unlisted."""
    for name in ARTICLES + ['unlisted']:
        response = fetch(f'/articles/{name}')
        assert response.status == 200, name
        assert f'<title>{article(name).title}</title>' in response.body.decode()
        assert _words(response) >= 250
        assert _links(response) == (['/articles/unlisted'] if name == 'crumb' else []), name
    assert fetch('/articles/other').status == 404
    assert fetch('/articles/starter/more').status == 404


def test_notes(fetch):
    """/notes/ links to two articles and two notes; each note is an article with no links."""
    assert _links(fetch('/notes/')) == ['/articles/steam', '/articles/crumb', '/notes/flour', '/notes/salt']
    assert _words(fetch('/notes/')) >= 250
    for name in ('flour', 'salt'):
        response = fetch(f'/notes/{name}')
        assert response.status == 200 and _links(response) == [] and _words(response) >= 250
    assert fetch('/notes/sugar').status == 404


def test_daily_section_links_seven_days(fetch):
    """/daily/ links to the request date and the six dates before it, newest first."""
    response = fetch('/daily/')
    assert _links(response) == [f'/daily/2026-11-{day}' for day in range(25, 18, -1)]
    assert _words(response) >= 250
    assert response.headers['last-modified'] == 'Wed, 25 Nov 2026 00:00:00 GMT'
    early = fetch('/daily/', now=datetime(2026, 1, 2, 8, tzinfo=timezone.utc))
    assert _links(early)[:3] == ['/daily/2026-01-02', '/daily/2026-01-01', '/daily/2025-12-31']


def test_daily_section_follows_date_header(fetch):
    """X-Pathological-Date moves the daily links."""
    response = fetch('/daily/', headers={'x-pathological-date': '2026-03-01'})
    assert _links(response)[0] == '/daily/2026-03-01'


def test_daily_pages(fetch):
    """A daily page is an article of its date; a future, early or invalid date is 404."""
    response = fetch('/daily/2026-11-20')
    assert response.status == 200 and _words(response) >= 250 and _links(response) == []
    assert response.headers['last-modified'] == 'Fri, 20 Nov 2026 00:00:00 GMT'
    assert fetch('/daily/2026-11-25').status == 200
    assert fetch('/daily/2026-01-01').status == 200
    assert fetch('/daily/2026-11-26').status == 404
    assert fetch('/daily/2025-12-31').status == 404
    assert fetch('/daily/2026-02-30').status == 404
    assert fetch('/daily/20261120').status == 404
    assert fetch('/daily/tomorrow').status == 404
    assert fetch('/daily/2026-11-26', headers={'x-pathological-date': '2026-11-26'}).status == 200


def test_daily_pages_differ(fetch):
    """Two daily pages have different titles."""
    assert fetch('/daily/2026-11-20').body != fetch('/daily/2026-11-21').body


def test_find_exact_and_patterns():
    """find matches exact paths before patterns; a pattern segment matches one non-empty segment."""
    assert find('/articles/').name == find('/articles/').name != find('/articles/x').name
    assert find('/articles/x').paths == ('/articles/<name>',)
    assert find('/articles/x/y') is None
    assert find('/nowhere') is None
    assert find('/notes/flour') is find('/notes/salt')


def test_cases_family_order():
    """cases() starts with the regulars and each case has paths and a behavior."""
    all_cases = cases()
    assert all_cases[0].family == 'regulars'
    assert all(isinstance(c, Case) and c.paths and c.behavior for c in all_cases)


def test_section_case():
    """section_case serves /<family>/ as an article page with the given title, followed by the links."""
    case = section_case('tangle', 'Tangled links of sourdough baking', ['/tangle/a', ('/tangle/b', 'B')])
    assert case.family == 'tangle' and case.paths == ('/tangle/',)
    response = case.handler(Request(host='tangle.localhost', path='/tangle/'))
    body = response.body.decode()
    assert '<title>Tangled links of sourdough baking</title>' in body
    assert _links(response) == ['/tangle/a', '/tangle/b']
    assert _words(response) >= 250
