import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

from afm_pathological.hosts import HOSTS
from afm_pathological.model import Request
from afm_pathological.sitemaps import regular_urls, sitemap_index, urlset

NOW = datetime(2026, 11, 25, 12, 0, 45, tzinfo=timezone.utc)
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
SPEC_HOSTS = {
    'breadcrumbs': 'First', 'librarian': 'First', 'town-crier': 'First', 'mirage': 'First',
    'chicken-little': 'Next', 'rip-van-winkle': 'Next', 'hoarder': 'Next', 'squirrel': 'Next',
    'headless-horseman': 'Next', 'tipsy-cartographer': 'Later', 'gutenberg': 'Later', 'yes-man': 'Later',
    'sloth': 'Later', 'whisperer': 'Later', 'masquerade': 'Later', 'janus': 'Later', 'forwarding-address': 'Later',
    'doorman': 'Later',
}


def test_hosts_table():
    """HOSTS has the 18 hosts of the spec with their build and the cells of the table."""
    assert {name: spec.build for name, spec in HOSTS.items()} == SPEC_HOSTS
    assert all(spec.name == name and spec.character and spec.root_says for name, spec in HOSTS.items())
    assert HOSTS['mirage'].character == 'Promises a map that is not there'
    assert HOSTS['mirage'].root_says == '`robots.txt` lists `/sitemap.xml`, which answers 404'


def test_root_urls_match_responses(fetch):
    """Each RootUrl of each host gives its status and content type on a GET."""
    assert {u.path for u in HOSTS['librarian'].root_urls} == {'/robots.txt', '/sitemap.xml'}
    assert {(u.path, u.status) for u in HOSTS['mirage'].root_urls} == {('/robots.txt', 200), ('/sitemap.xml', 404)}
    assert [u.path for u in HOSTS['breadcrumbs'].root_urls] == ['/robots.txt']
    for name, spec in HOSTS.items():
        for url in spec.root_urls:
            response = fetch(url.path, host=name)
            assert response.status == url.status, (name, url.path)
            assert response.headers['content-type'].startswith(url.content_type), (name, url.path)


def test_breadcrumbs_robots(fetch):
    """breadcrumbs has a robots.txt that disallows all, with no Sitemap line."""
    response = fetch('/robots.txt', host='breadcrumbs')
    assert response.status == 200
    assert response.headers['content-type'].startswith('text/plain')
    assert response.body.decode() == 'User-agent: *\nDisallow: /\n'


def test_librarian_and_mirage_robots(fetch):
    """librarian and mirage list the absolute URL of their /sitemap.xml."""
    for name in ('librarian', 'mirage'):
        body = fetch('/robots.txt', host=name).body.decode()
        assert body == f'User-agent: *\nDisallow: /\nSitemap: https://{name}.pathological.answersfrom.me/sitemap.xml\n'


def test_librarian_sitemap(fetch):
    """librarian's sitemap lists the 18 regular URLs with true lastmod dates and a matching Last-Modified."""
    response = fetch('/sitemap.xml', host='librarian')
    assert response.status == 200
    assert response.headers['content-type'] == 'application/xml'
    assert response.headers['last-modified'] == 'Wed, 25 Nov 2026 00:00:00 GMT'
    root = ET.fromstring(response.body)
    entries = {u.find(f'{NS}loc').text: u.find(f'{NS}lastmod').text for u in root.findall(f'{NS}url')}
    base = 'https://librarian.pathological.answersfrom.me'
    assert len(entries) == 18
    assert entries[f'{base}/'] == '2026-01-01'
    assert entries[f'{base}/daily/'] == '2026-11-25'
    assert entries[f'{base}/daily/2026-11-19'] == '2026-11-19'
    assert entries[f'{base}/articles/crumb'] == '2026-01-01'
    assert f'{base}/articles/unlisted' not in entries
    assert f'{base}/daily/2026-11-18' not in entries


def test_librarian_sitemap_conditional(fetch):
    """The sitemap answers 304 to its own validators and 200 after the date changes."""
    first = fetch('/sitemap.xml', host='librarian')
    assert fetch('/sitemap.xml', host='librarian', headers={'if-none-match': first.headers['etag']}).status == 304
    since = {'if-modified-since': first.headers['last-modified']}
    assert fetch('/sitemap.xml', host='librarian', headers=since).status == 304
    later = {**since, 'x-pathological-date': '2026-11-26'}
    assert fetch('/sitemap.xml', host='librarian', headers=later).status == 200


def test_mirage_sitemap_missing(fetch):
    """mirage's /sitemap.xml answers 404."""
    assert fetch('/sitemap.xml', host='mirage').status == 404
    assert fetch('/sitemap.xml', host='breadcrumbs').status == 404


def test_regular_urls():
    """regular_urls gives the 18 regular URLs with the date of their last change."""
    urls = regular_urls(Request(host='Janus.Localhost:8080', path='/sitemap.xml', now=NOW, scheme='http'))
    assert len(urls) == 18
    assert urls[0] == ('http://janus.localhost:8080/', date(2026, 1, 1))
    paths = [u.removeprefix('http://janus.localhost:8080') for u, _ in urls]
    assert paths[:9] == ['/', '/articles/', '/notes/', '/daily/', '/articles/starter', '/articles/hydration',
                         '/articles/scoring', '/articles/steam', '/articles/crumb']
    assert paths[9:11] == ['/notes/flour', '/notes/salt']
    assert paths[11:] == [f'/daily/2026-11-{day}' for day in range(25, 18, -1)]
    assert dict(urls)['http://janus.localhost:8080/daily/2026-11-20'] == date(2026, 11, 20)


def test_urlset_and_index():
    """urlset and sitemap_index write the sitemap namespace, an XML declaration and escaped locs."""
    body = urlset([('https://x/a?b=1&c=2', '2026-01-01'), ('https://x/b', None)])
    assert body.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    root = ET.fromstring(body)
    assert root.tag == f'{NS}urlset'
    assert [u.find(f'{NS}loc').text for u in root] == ['https://x/a?b=1&c=2', 'https://x/b']
    assert root[1].find(f'{NS}lastmod') is None
    index = ET.fromstring(sitemap_index(['https://x/1.xml', 'https://x/2.xml']))
    assert index.tag == f'{NS}sitemapindex'
    assert [s.find(f'{NS}loc').text for s in index] == ['https://x/1.xml', 'https://x/2.xml']
    assert re.search(r'<lastmod>', sitemap_index(['https://x/1.xml'])) is None
