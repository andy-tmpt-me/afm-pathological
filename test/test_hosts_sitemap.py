import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pytest

from afm_pathological.families.feeds import daily_rss
from afm_pathological.hosts import HOSTS
from afm_pathological.model import Request
from afm_pathological.site import respond

NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
NOW = datetime(2026, 11, 25, 12, 0, 45, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 25, 13, 14, 15, tzinfo=timezone.utc)
STAMP = '2026-11-25T12:00:45Z'
BASE = 'https://{}.pathological.answersfrom.me'


def entries(source):
    """The (loc, lastmod) pairs of a <urlset> given as a response or as bytes."""
    root = ET.fromstring(getattr(source, 'body', source))
    assert root.tag == f'{NS}urlset'
    return [(u.find(f'{NS}loc').text, getattr(u.find(f'{NS}lastmod'), 'text', None)) for u in root]


def sitemap_lines(response):
    """The values of the Sitemap lines of a robots.txt response."""
    return [line.split(': ', 1)[1] for line in response.body.decode().splitlines() if line.startswith('Sitemap: ')]


def test_chicken_little_lastmod_is_now(fetch):
    """Each lastmod is the time of the request; the 18 URLs are those of librarian."""
    response = fetch('/sitemap.xml', host='chicken-little')
    assert response.status == 200 and response.headers['content-type'] == 'application/xml'
    parsed = entries(response)
    assert len(parsed) == 18
    assert {lastmod for _, lastmod in parsed} == {STAMP}
    librarian = entries(fetch('/sitemap.xml', host='librarian'))
    assert [loc.replace('librarian', 'chicken-little') for loc, _ in librarian] == [loc for loc, _ in parsed]
    robots = fetch('/robots.txt', host='chicken-little')
    assert sitemap_lines(robots) == [BASE.format('chicken-little') + '/sitemap.xml']


def test_chicken_little_headers_change_bodies_do_not(fetch):
    """The ETag and Last-Modified follow the request time, on every 200; page bodies stay equal; no 304."""
    first = fetch('/articles/starter', host='chicken-little')
    second = fetch('/articles/starter', host='chicken-little', now=LATER)
    assert first.body == second.body
    assert first.headers['last-modified'] == 'Wed, 25 Nov 2026 12:00:45 GMT'
    assert second.headers['last-modified'] == 'Wed, 25 Nov 2026 13:14:15 GMT'
    assert first.headers['etag'] != second.headers['etag']
    assert fetch('/sitemap.xml', host='chicken-little').headers['etag'] == first.headers['etag']
    conditional = {'if-none-match': first.headers['etag'], 'if-modified-since': 'Wed, 25 Nov 2026 12:00:45 GMT'}
    again = fetch('/articles/starter', host='chicken-little', now=LATER, headers=conditional)
    assert again.status == 200 and again.body == first.body
    assert fetch('/nothing', host='chicken-little').headers.get('etag') is None


def test_rip_van_winkle_sitemap(fetch):
    """The sitemap lists 20 URLs, all with lastmod 2026-01-01; the two last are chameleons pages."""
    parsed = entries(fetch('/sitemap.xml', host='rip-van-winkle'))
    base = BASE.format('rip-van-winkle')
    assert len(parsed) == 20
    assert {lastmod for _, lastmod in parsed} == {'2026-01-01'}
    librarian = entries(fetch('/sitemap.xml', host='librarian'))
    assert [loc for loc, _ in parsed[:18]] == [loc.replace('librarian', 'rip-van-winkle') for loc, _ in librarian]
    assert [loc for loc, _ in parsed[18:]] == [f'{base}/chameleons/honest-edit', f'{base}/chameleons/silent-edit']
    assert sitemap_lines(fetch('/robots.txt', host='rip-van-winkle')) == [f'{base}/sitemap.xml']


def test_rip_van_winkle_constant_headers_and_304(fetch):
    """Each 200 has the same ETag and Last-Modified at any time; a conditional request answers 304."""
    first = fetch('/sitemap.xml', host='rip-van-winkle')
    later = fetch('/articles/crumb', host='rip-van-winkle', now=LATER)
    for response in (first, later):
        assert response.headers['etag'] == '"rip"'
        assert response.headers['last-modified'] == 'Thu, 01 Jan 2026 00:00:00 GMT'
    for conditional in ({'if-none-match': '"x"'}, {'if-modified-since': 'Mon, 01 Jan 2001 00:00:00 GMT'}):
        for path in ('/', '/sitemap.xml', '/anything'):
            response = fetch(path, host='rip-van-winkle', headers=conditional)
            assert response.status == 304 and response.body == b''


def test_hoarder(fetch):
    """robots lists the index; the index lists five sitemaps; they list 100 URLs each, the last 107: 507 in all."""
    base = BASE.format('hoarder')
    assert sitemap_lines(fetch('/robots.txt', host='hoarder')) == [f'{base}/sitemap_index.xml']
    index = ET.fromstring(fetch('/sitemap_index.xml', host='hoarder').body)
    assert index.tag == f'{NS}sitemapindex'
    assert [s.find(f'{NS}loc').text for s in index] == [f'{base}/sitemaps/{n}.xml' for n in range(1, 6)]
    assert not list(index.iter(f'{NS}lastmod'))
    parsed = [entries(fetch(f'/sitemaps/{n}.xml', host='hoarder')) for n in range(1, 6)]
    assert [len(p) for p in parsed] == [100, 100, 100, 100, 107] and sum(len(p) for p in parsed) == 507
    hoard = [loc for p in parsed[:4] for loc, _ in p] + [loc for loc, _ in parsed[4][:100]]
    assert hoard == [f'{base}/hoard/{n}' for n in range(1, 501)]
    assert [loc for loc, _ in parsed[4][100:]] == [f'{base}/daily/2026-11-{d}' for d in range(25, 18, -1)]
    assert all(lastmod is None for p in parsed for _, lastmod in p)
    for missing in ('0', '6', '10', '01'):
        assert fetch(f'/sitemaps/{missing}.xml', host='hoarder').status == 404
    assert fetch('/sitemap.xml', host='hoarder').status == 404


def test_hoard_pages(fetch):
    """/hoard/1 to /hoard/500 are articles on every host; others are 404."""
    for host in ('breadcrumbs', 'hoarder'):
        for n in ('1', '180', '500'):
            assert fetch(f'/hoard/{n}', host=host).status == 200
    assert fetch('/hoard/1').body != fetch('/hoard/2').body
    for bad in ('0', '501', '01', 'x', '-1'):
        assert fetch(f'/hoard/{bad}', host='hoarder').status == 404


def test_squirrel(fetch):
    """The sitemap has the 18 URLs with no lastmod; robots.txt is 404."""
    parsed = entries(fetch('/sitemap.xml', host='squirrel'))
    assert len(parsed) == 18 and all(lastmod is None for _, lastmod in parsed)
    assert fetch('/robots.txt', host='squirrel').status == 404


TIPSY = 'tipsy-cartographer.pathological.answersfrom.me'


@pytest.fixture
def tipsy():
    """A function that sends a GET with an optional query to tipsy-cartographer."""
    return lambda path, query='': respond(Request(TIPSY, path, query=query, now=NOW))


def maps(response):
    """The paths of the Sitemap lines of a robots.txt response, without the host."""
    return [url.removeprefix(BASE.format('tipsy-cartographer')) for url in sitemap_lines(response)]


def test_tipsy_robots(tipsy):
    """With no query robots.txt lists the five sitemaps."""
    response = tipsy('/robots.txt')
    assert response.body.decode().startswith('User-agent: *\nDisallow: /\n')
    assert maps(response) == ['/maps/good.xml', '/maps/missing.xml', '/maps/feed.xml', '/maps/elsewhere.xml',
                              '/maps/malformed.xml']


@pytest.mark.parametrize('case, listed', [
    ('nested', ['/maps/index-broken.xml']), ('after', ['/maps/good.xml', '/maps/text-after.xml']),
    ('no-namespace', ['/maps/good.xml', '/maps/no-namespace.xml']), ('latin1', ['/maps/good.xml', '/maps/latin1.xml']),
    ('gz', ['/maps/good.xml', '/maps/good.xml.gz']), ('self', ['/maps/self-index.xml']),
    ('other', ['/maps/good.xml', '/maps/missing.xml', '/maps/feed.xml', '/maps/elsewhere.xml',
               '/maps/malformed.xml'])])
def test_tipsy_robots_variants(tipsy, case, listed):
    """Each case of robots.txt lists the sitemaps of ROBOTS_CASES; an unknown case gives the default."""
    assert maps(tipsy('/robots.txt', f'case={case}')) == listed


def test_tipsy_robots_forms(tipsy):
    """The forms case has the three lines of the spec: an absolute URL, a commented one and a relative one."""
    lines = [line for line in tipsy('/robots.txt', 'case=forms').body.decode().splitlines() if 'Sitemap' in line]
    assert lines == [f'Sitemap: {BASE.format("tipsy-cartographer")}/maps/good.xml', '# Sitemap: /maps/old.xml',
                     'Sitemap: /maps/relative.xml']
    for path in ('/maps/relative.xml', '/maps/old.xml'):
        assert len(entries(tipsy(path))) == 1


def test_tipsy_good_has_php_warning(tipsy):
    """good.xml has a PHP warning before <?xml and then the 18 URLs."""
    response = tipsy('/maps/good.xml')
    body = response.body.decode()
    assert response.status == 200 and response.headers['content-type'] == 'application/xml'
    assert body.startswith('<br />\n<b>Warning</b>: Undefined variable $x in <b>/var/www/sitemap.php</b>\n<?xml')
    assert len(entries(body[body.index('<?xml'):].encode())) == 18


def test_tipsy_missing_feed_elsewhere_malformed(tipsy):
    """missing is 404, feed is the daily RSS, elsewhere has two URLs of other hosts, malformed does not parse."""
    assert tipsy('/maps/missing.xml').status == 404
    feed = tipsy('/maps/feed.xml')
    assert feed.headers['content-type'].startswith('application/rss+xml')
    assert feed.body == daily_rss(Request(TIPSY, '/feed', now=NOW)).body
    assert [loc for loc, _ in entries(tipsy('/maps/elsewhere.xml'))] == [
        'https://librarian.pathological.answersfrom.me/articles/starter', 'https://example.com/']
    response = tipsy('/maps/malformed.xml')
    assert response.status == 200 and response.body.startswith(b'<?xml')
    assert b'<loc>' in response.body and not response.body.rstrip().endswith(b'</urlset>')
    with pytest.raises(ET.ParseError):
        ET.fromstring(response.body)


def test_tipsy_elsewhere_names_librarian_on_the_same_domain():
    """The librarian URL of elsewhere follows the host and the scheme of the request; example.com stays."""
    local = respond(Request('tipsy-cartographer.localhost:8080', '/maps/elsewhere.xml', scheme='http', now=NOW))
    assert [loc for loc, _ in entries(local)] == ['http://librarian.localhost:8080/articles/starter',
                                                  'https://example.com/']


def test_tipsy_index_broken_and_self(tipsy):
    """index-broken lists good and missing; self-index lists itself."""
    base = BASE.format('tipsy-cartographer')
    for path, listed in (('/maps/index-broken.xml', [f'{base}/maps/good.xml', f'{base}/maps/missing.xml']),
                         ('/maps/self-index.xml', [f'{base}/maps/self-index.xml'])):
        root = ET.fromstring(tipsy(path).body)
        assert root.tag == f'{NS}sitemapindex'
        assert [s.find(f'{NS}loc').text for s in root] == listed


def test_tipsy_text_after_and_no_namespace(tipsy):
    """text-after has text after </urlset>; no-namespace has a <urlset> with no xmlns. Neither parses as a sitemap."""
    body = tipsy('/maps/text-after.xml').body
    with pytest.raises(ET.ParseError):
        ET.fromstring(body)
    assert body.count(b'<loc>') > 0 and not body.rstrip().endswith(b'</urlset>')
    root = ET.fromstring(tipsy('/maps/no-namespace.xml').body)
    assert root.tag == 'urlset' and len(root) == 18 and root[0].find('loc').text


def test_tipsy_latin1_and_gz(tipsy):
    """latin1 has Latin-1 bytes and a utf-8 header; gz is gzip bytes with no content-encoding."""
    response = tipsy('/maps/latin1.xml')
    assert response.headers['content-type'] == 'application/xml; charset=utf-8'
    assert b'caf\xe9' in response.body
    with pytest.raises(UnicodeDecodeError):
        response.body.decode()
    gz = tipsy('/maps/good.xml.gz')
    assert gz.headers['content-type'] == 'application/gzip' and 'content-encoding' not in gz.headers
    assert gz.body[:2] == b'\x1f\x8b'
    assert len(entries(gzip.decompress(gz.body))) == 18


def test_janus_sitemap(fetch):
    """Both names give the same sitemap: 18 apex URLs and, after /articles/starter, the www and upper-case forms."""
    apex = 'janus.pathological.answersfrom.me'
    expected = [f'https://{apex}/articles/starter', f'https://www.{apex}/articles/starter',
                f'https://{apex.upper()}/articles/starter']
    for host in ('janus.pathological.answersfrom.me', 'www.janus.pathological.answersfrom.me'):
        response = fetch('/sitemap.xml', host=host)
        assert response.status == 200 and response.headers['content-type'] == 'application/xml'
        locs = [loc for loc, _ in entries(response)]
        assert len(locs) == 20
        start = locs.index(expected[0])
        assert locs[start:start + 3] == expected
        assert all(loc.startswith(f'https://{apex}/') for loc in locs if loc not in expected)
        assert sitemap_lines(fetch('/robots.txt', host=host)) == [f'https://{host}/sitemap.xml']
    assert fetch('/sitemap.xml', host='janus.pathological.answersfrom.me').body == fetch(
        '/sitemap.xml', host='www.janus.pathological.answersfrom.me').body


def test_janus_local_host_with_port(fetch):
    """The apex name keeps the port of the request host."""
    locs = [loc for loc, _ in entries(fetch('/sitemap.xml', host='www.janus.localhost:8080'))]
    assert locs[0] == 'https://janus.localhost:8080/'


def test_root_urls_of_sitemap_hosts():
    """Each host lists the host-root URLs of this task."""
    paths = {name: [u.path for u in HOSTS[name].root_urls] for name in HOSTS}
    assert paths['chicken-little'] == paths['rip-van-winkle'] == ['/robots.txt', '/sitemap.xml']
    assert paths['hoarder'] == ['/robots.txt', '/sitemap_index.xml'] + [f'/sitemaps/{n}.xml' for n in range(1, 6)]
    assert paths['squirrel'] == ['/sitemap.xml']
    assert paths['janus'] == ['/robots.txt', '/sitemap.xml']
    assert {'/maps/good.xml', '/maps/missing.xml', '/maps/feed.xml'} <= set(paths['tipsy-cartographer'])
