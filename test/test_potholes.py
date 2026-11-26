import re
from datetime import datetime, timezone

import pytest

from afm_pathological.catalog import cases

NOW = datetime(2026, 11, 25, 12, 0, 45, tzinfo=timezone.utc)
ERROR_SLOT = NOW.replace(second=10)


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def _title(response) -> str:
    """The <title> of a response body."""
    return re.search(r'<title>(.*?)</title>', response.body.decode()).group(1)


def test_section_links(fetch):
    """The section page links to every case path, and cases have the tags of the spec."""
    body = fetch('/potholes/').body.decode()
    links = re.findall(r'<a href="([^"]*)"', body)
    assert links[:6] == [f'/potholes/status/{code}' for code in (403, 404, 410, 429, 500, 503)]
    assert {'/potholes/soft-404', '/potholes/fails-first', '/potholes/slow-get', '/potholes/slow-head',
            '/potholes/torn', '/potholes/empty', '/potholes/xml-typed', '/potholes/fake.pdf', '/potholes/fake.mp3',
            '/potholes/challenge.mp3', '/potholes/blob.xyz', '/potholes/latin1', '/potholes/bad-date',
            '/potholes/brotli', '/potholes/not-gzip'} <= set(links)
    assert all(fetch(link).status in (200, 403, 404, 410, 429, 500, 503) for link in links)
    tags = {c.name: c.tags for c in cases() if c.family == 'potholes'}
    assert tags['fails-first'] == ('local only',) and tags['slow'] == ('local only',)


@pytest.mark.parametrize('code', [403, 404, 410, 429, 500, 503])
def test_status(fetch, code):
    """Each status path answers its status with a short HTML body and no validators."""
    response = fetch(f'/potholes/status/{code}')
    assert response.status == code and response.body and 'etag' not in response.headers
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert response.headers.get('retry-after') == ('30' if code == 429 else None)
    assert fetch('/potholes/status/418').status == 404


def test_soft_404(fetch):
    """200 with the title 'Page not found' and one sentence."""
    response = fetch('/potholes/soft-404')
    assert response.status == 200 and _title(response) == 'Page not found'
    assert len(re.findall(r'<p>', response.body.decode())) == 1


def test_fails_first(fetch):
    """503 in seconds 0 to 29, an article in seconds 30 to 59."""
    assert fetch('/potholes/fails-first', now=ERROR_SLOT).status == 503
    assert fetch('/potholes/fails-first', now=ERROR_SLOT.replace(second=29)).status == 503
    ok = fetch('/potholes/fails-first', now=NOW.replace(second=30))
    assert ok.status == 200 and _words(ok) >= 250


def test_slow(fetch):
    """slow-get waits 35 s for GET only; slow-head waits 12 s for HEAD only."""
    assert fetch('/potholes/slow-get').delay_sec == 35
    assert fetch('/potholes/slow-get', method='HEAD').delay_sec == 0
    assert fetch('/potholes/slow-head', method='HEAD').delay_sec == 12
    get = fetch('/potholes/slow-head')
    assert get.delay_sec == 0 and get.status == 200 and _words(get) >= 250


def test_torn(fetch):
    """The page is exactly 10,000 bytes and the connection closes after 2,000."""
    response = fetch('/potholes/torn')
    assert response.tear_after == 2000 and len(response.body) == 10000
    assert response.headers['content-length'] == '10000'
    assert response.headers['content-length'] == str(len(response.body))


def test_empty(fetch):
    """200, text/html, no body, content-length 0."""
    response = fetch('/potholes/empty')
    assert response.status == 200 and response.body == b'' and response.headers['content-length'] == '0'
    assert response.headers['content-type'].startswith('text/html') and 'etag' not in response.headers


def test_xml_typed(fetch):
    """An HTML article with the XML content type."""
    response = fetch('/potholes/xml-typed')
    assert response.headers['content-type'] == 'application/xml' and _words(response) >= 250


@pytest.mark.parametrize('path', ['/potholes/fake.pdf', '/potholes/fake.mp3'])
def test_fake_files(fetch, path):
    """An HTML article at a file URL."""
    response = fetch(path)
    assert response.headers['content-type'] == 'text/html; charset=utf-8' and _words(response) >= 250
    assert not response.body.startswith(b'%PDF')


def test_challenge_mp3(fetch):
    """A challenge page at an MP3 URL."""
    response = fetch('/potholes/challenge.mp3')
    assert response.headers['content-type'].startswith('text/html')
    assert _title(response) == 'Just a moment...' and 'cf-chl' in response.body.decode()


def test_blob(fetch):
    """1,024 bytes of a fixed pattern with an unknown type."""
    response = fetch('/potholes/blob.xyz')
    assert response.headers['content-type'] == 'application/x-unknown' and len(response.body) == 1024
    assert response.body == fetch('/potholes/blob.xyz').body


def test_latin1(fetch):
    """Latin-1 bytes under a utf-8 header."""
    response = fetch('/potholes/latin1')
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert 'café'.encode('latin-1') in response.body
    with pytest.raises(UnicodeDecodeError):
        response.body.decode('utf-8')


def test_bad_date(fetch):
    """Last-Modified is not an HTTP date, and the site keeps it."""
    response = fetch('/potholes/bad-date')
    assert response.headers['last-modified'] == '2026-11-25T00:00:00Z' and _words(response) >= 250
    assert fetch('/potholes/bad-date', headers={'if-modified-since': 'Thu, 01 Jan 2026 00:00:00 GMT'}).status == 200


def test_brotli(fetch):
    """The Brotli header with a body that is not UTF-8 text."""
    response = fetch('/potholes/brotli')
    assert response.headers['content-encoding'] == 'br'
    with pytest.raises(UnicodeDecodeError):
        response.body.decode('utf-8')


def test_not_gzip(fetch):
    """Plain article bytes under a gzip header."""
    response = fetch('/potholes/not-gzip')
    assert response.headers['content-encoding'] == 'gzip' and not response.body.startswith(b'\x1f\x8b')
    assert _words(response) >= 250


def test_head_keeps_length(fetch):
    """A HEAD of torn has no body and the content-length of the GET."""
    head = fetch('/potholes/torn', method='HEAD')
    assert head.body == b'' and head.headers['content-length'] == str(len(fetch('/potholes/torn').body))
