import re
from xml.etree import ElementTree

import pytest

from afm_pathological.catalog import cases
from afm_pathological.families.attic import _large


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def _body(response) -> str:
    """The decoded body of a response."""
    return response.body.decode()


def test_section_links(fetch):
    """The section page links to the cases that are not own sources."""
    assert re.findall(r'<a href="([^"]*)"', _body(fetch('/attic/'))) == [
        '/attic/no-text', '/attic/embedded', '/attic/paper.pdf', '/attic/paper', '/attic/no-title', '/attic/og-only',
        '/attic/svg-image', '/attic/canonical-no-href', '/attic/french']
    tags = {c.name: c.tags for c in cases() if c.family == 'attic'}
    assert tags['large-page'] == tags['not-relevant'] == ('own source',)


def test_no_text(fetch):
    """The body is one image and nothing else."""
    body = _body(fetch('/attic/no-text'))
    assert re.search(r'<body>\s*<img src="/tangle/files/photo.jpg" alt="A loaf of bread">\s*</body>', body)


def test_large(fetch):
    """2,000 paragraphs, between 5,000,000 and 5,242,880 bytes."""
    response = fetch('/attic/large')
    assert 5_000_000 <= len(response.body) <= 5_242_880
    assert _body(response).count('<p>') == 2000 and response.headers['content-type'] == 'text/html; charset=utf-8'


def test_embedded(fetch):
    """A YouTube frame, a Vimeo frame, an audio element and a tracked download link."""
    body = _body(fetch('/attic/embedded'))
    assert '<iframe src="https://www.youtube.com/embed/M7lc1UVf-VE">' in body
    assert '<iframe src="https://player.vimeo.com/video/76979871">' in body
    assert '<audio src="/tangle/files/talk.mp3">' in body
    assert '<a href="/tangle/files/talk.mp3?utm_source=player">Download the episode</a>' in body
    assert _words(fetch('/attic/embedded')) >= 250


@pytest.mark.parametrize('path', ['/attic/paper.pdf', '/attic/paper'])
def test_pdf(fetch, path):
    """A PDF with and without the extension."""
    response = fetch(path)
    assert response.headers['content-type'] == 'application/pdf' and response.body.startswith(b'%PDF')


def test_sitemap(fetch):
    """The four absolute URLs of the spec."""
    response = fetch('/attic/sitemap.xml', host='librarian.pathological.answersfrom.me')
    assert response.headers['content-type'] == 'application/xml'
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    locs = [e.text for e in ElementTree.fromstring(response.body).findall('s:url/s:loc', ns)]
    host = 'https://librarian.pathological.answersfrom.me'
    assert locs == [f'{host}/attic/privacy-policy', f'{host}/attic/careers', f'{host}/articles/starter',
                    f'{host}/articles/steam']


@pytest.mark.parametrize('path', ['/attic/privacy-policy', '/attic/careers'])
def test_plain_pages(fetch, path):
    """Long pages that are not about baking."""
    response = fetch(path)
    assert _words(response) >= 250 and 'sourdough' not in _body(response).lower()
    assert len(re.search(r'<title>(.*?)</title>', _body(response)).group(1)) > 10


def test_metadata_pages(fetch):
    """No title; Open Graph only; an SVG image; a canonical with no href."""
    no_title = _body(fetch('/attic/no-title'))
    assert '<title' not in no_title and _words(fetch('/attic/no-title')) >= 250
    og_only = _body(fetch('/attic/og-only'))
    assert '<title' not in og_only and '<meta property="og:title" content="' in og_only
    assert '<meta property="og:description" content="' in og_only
    svg_page = _body(fetch('/attic/svg-image'))
    assert '<meta property="og:image" content="/attic/loaf.svg">' in svg_page
    svg = fetch('/attic/loaf.svg')
    assert svg.headers['content-type'] == 'image/svg+xml' and len(svg.body) < 2000
    ElementTree.fromstring(svg.body)
    canonical = _body(fetch('/attic/canonical-no-href'))
    assert '<link rel="canonical">' in canonical and _words(fetch('/attic/canonical-no-href')) >= 250


def test_french(fetch):
    """A French article of 250 words or more about sourdough."""
    response = fetch('/attic/french')
    assert _words(response) >= 250 and 'levain' in _body(response) and '<html lang="fr">' in _body(response)


def test_large_shares_the_cached_bytes(fetch):
    """Each response of the large page holds the one cached body, not a copy of 5 MB."""
    assert fetch('/attic/large').body is _large() and fetch('/attic/large').body is _large()
