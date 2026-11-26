import json
from datetime import datetime, timezone

from afm_pathological.hosts import HOSTS, resolve


def test_unknown_host_lists_hosts(fetch):
    """An unknown host answers 404 with a plain-text list of the host names on a path other than its landing paths."""
    assert fetch('/', host='nobody').status == 200
    response = fetch('/articles/starter', host='nobody')
    assert response.status == 404
    assert response.headers['content-type'].startswith('text/plain')
    for name in HOSTS:
        assert name in response.body.decode()


def test_resolve_host_forms():
    """Letter case, a port, www. and localhost forms resolve to the host spec."""
    assert resolve('librarian.pathological.answersfrom.me') == (HOSTS['librarian'], False)
    assert resolve('LIBRARIAN.Pathological.AnswersFrom.Me') == (HOSTS['librarian'], False)
    assert resolve('librarian.pathological.answersfrom.me:443') == (HOSTS['librarian'], False)
    assert resolve('mirage.localhost:8080') == (HOSTS['mirage'], False)
    assert resolve('www.janus.pathological.answersfrom.me') == (HOSTS['janus'], True)
    assert resolve('janus.pathological.answersfrom.me') == (HOSTS['janus'], False)
    assert resolve('nobody.localhost') == (None, False)


def test_host_header_forms_respond(fetch):
    """Upper case, a port and localhost Host headers all reach the host."""
    for host in ('BREADCRUMBS.PATHOLOGICAL.ANSWERSFROM.ME', 'breadcrumbs.pathological.answersfrom.me:443',
                 'breadcrumbs.localhost:8080', 'www.janus.localhost'):
        assert fetch('/articles/', host=host).status == 200, host


def test_host_override_header(fetch):
    """The x-pathological-host header replaces the Host header."""
    response = fetch('/robots.txt', host='localhost:8080', headers={'x-pathological-host': 'librarian.localhost:8080'})
    assert 'Sitemap: https://librarian.localhost:8080/sitemap.xml' in response.body.decode()


def test_clock(fetch):
    """/clock returns the time, the date in effect and the day number, with no validators."""
    response = fetch('/clock', host='mirage')
    assert json.loads(response.body) == {'utc': '2026-11-25T12:00:45+00:00', 'date': '2026-11-25', 'day_number': 328}
    assert 'etag' not in response.headers and 'last-modified' not in response.headers
    shifted = json.loads(fetch('/clock', headers={'x-pathological-date': '2026-01-02'}).body)
    assert shifted['date'] == '2026-01-02' and shifted['day_number'] == 1


def test_validators_added_to_200(fetch):
    """A 200 response gets a quoted ETag, a Last-Modified and a content-length."""
    response = fetch('/articles/starter')
    assert response.headers['etag'].startswith('"') and response.headers['etag'].endswith('"')
    assert response.headers['last-modified'] == 'Thu, 01 Jan 2026 00:00:00 GMT'
    assert response.headers['content-length'] == str(len(response.body))


def test_etag_follows_body(fetch):
    """Two pages with different bodies have different ETags; the same page keeps its ETag."""
    first = fetch('/articles/starter').headers['etag']
    assert fetch('/articles/starter', now=datetime(2026, 5, 1, tzinfo=timezone.utc)).headers['etag'] == first
    assert fetch('/articles/steam').headers['etag'] != first


def test_if_none_match_gives_304(fetch):
    """If-None-Match equal to the ETag answers 304 with no body; a different value answers 200."""
    etag = fetch('/articles/starter').headers['etag']
    response = fetch('/articles/starter', headers={'if-none-match': etag})
    assert response.status == 304 and response.body == b''
    assert response.headers['etag'] == etag
    assert fetch('/articles/starter', headers={'if-none-match': '"other"'}).status == 200


def test_if_none_match_wins_over_if_modified_since(fetch):
    """With If-None-Match present, If-Modified-Since is ignored."""
    headers = {'if-none-match': '"other"', 'if-modified-since': 'Wed, 25 Nov 2026 00:00:00 GMT'}
    assert fetch('/articles/starter', headers=headers).status == 200


def test_if_modified_since(fetch):
    """If-Modified-Since not before Last-Modified answers 304; an earlier date or a bad value answers 200."""
    assert fetch('/articles/starter', headers={'if-modified-since': 'Thu, 01 Jan 2026 00:00:00 GMT'}).status == 304
    assert fetch('/articles/starter', headers={'if-modified-since': 'Wed, 25 Nov 2026 00:00:00 GMT'}).status == 304
    assert fetch('/articles/starter', headers={'if-modified-since': 'Wed, 31 Dec 2025 00:00:00 GMT'}).status == 200
    assert fetch('/articles/starter', headers={'if-modified-since': 'yesterday'}).status == 200


def test_no_validators_on_404(fetch):
    """A 404 has no ETag and never answers 304."""
    response = fetch('/articles/nothing', headers={'if-modified-since': 'Wed, 25 Nov 2026 00:00:00 GMT'})
    assert response.status == 404
    assert 'etag' not in response.headers and 'last-modified' not in response.headers


def test_head_has_no_body_and_same_length(fetch):
    """HEAD sends no body and the content-length of the GET body."""
    get = fetch('/articles/starter')
    head = fetch('/articles/starter', method='HEAD')
    assert head.status == 200 and head.body == b''
    assert head.headers['content-length'] == get.headers['content-length'] == str(len(get.body))
    assert head.headers['etag'] == get.headers['etag']


def test_unknown_path_404(fetch):
    """A path that no case serves answers 404."""
    assert fetch('/nothing/here').status == 404


def test_host_root_urls_404_without_root(fetch):
    """A host-root URL that the host does not serve answers 404."""
    for path in ('/sitemap.xml', '/feed', '/rss.xml', '/atom.xml', '/feed.xml', '/index.xml', '/rss2.xml',
                 '/wp-json/wp/v2/posts', '/wp-json/'):
        assert fetch(path, host='breadcrumbs').status == 404, path
