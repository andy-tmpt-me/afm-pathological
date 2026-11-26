import re
from html.parser import HTMLParser

from afm_pathological.catalog import cases

MARKERS = ('__NEXT_DATA__', 'window.__NUXT__', 'data-reactroot', '<app-root', 'ng-version', 'id="__next"',
           'id="root"', 'type="password"')


class _Words(HTMLParser):
    """Counts the words outside <script> elements and the <a href> links of the document."""

    def __init__(self):
        super().__init__()
        self.in_script, self.words, self.links = False, 0, []

    def handle_starttag(self, tag, attrs):
        self.in_script = tag == 'script'
        if tag == 'a':
            self.links.append(dict(attrs)['href'])

    def handle_endtag(self, tag):
        self.in_script = False

    def handle_data(self, data):
        if not self.in_script:
            self.words += len(data.split())


def _parse(response) -> _Words:
    """The word count and links of a response body."""
    parser = _Words()
    parser.feed(response.body.decode())
    return parser


def _paragraph_words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def test_section_links(fetch):
    """The section page links only to shell and short."""
    assert _parse(fetch('/holograms/')).links == ['/holograms/shell', '/holograms/short']
    assert {c.name: c.tags for c in cases() if c.family == 'holograms'}['shell'] == ('production only',)


def test_shell(fetch):
    """An empty container, a script that writes the article, fewer than 200 words outside the script."""
    response = fetch('/holograms/shell')
    body = response.body.decode()
    assert response.status == 200 and '<div id="app"></div>' in body and '<script>' in body
    assert _parse(response).words < 200 and '<p>' not in body.split('<script>')[0]
    assert not any(marker in body for marker in MARKERS)
    assert 'sourdough' in body.split('<script>')[1]


def test_short(fetch):
    """A server-rendered article of 150 words."""
    response = fetch('/holograms/short')
    assert _paragraph_words(response) == 150 and '<script' not in response.body.decode()


def test_script_links(fetch):
    """A long server-rendered article; a script adds three links, which are not in the HTML as <a>."""
    response = fetch('/holograms/script-links/')
    body = response.body.decode()
    assert _paragraph_words(response) >= 250 and _parse(response).links == []
    assert all(f'/holograms/script-links/{n}' in body.split('<script>')[1] for n in (1, 2, 3))
    for n in (1, 2, 3):
        child = fetch(f'/holograms/script-links/{n}')
        assert child.status == 200 and _paragraph_words(child) >= 250
    assert fetch('/holograms/script-links/4').status == 404


def test_mixed(fetch):
    """A server-rendered page with three real links, each to a shell page."""
    response = fetch('/holograms/mixed/')
    assert _paragraph_words(response) >= 250
    assert _parse(response).links == [f'/holograms/mixed/{n}' for n in (1, 2, 3)]
    bodies = []
    for n in (1, 2, 3):
        child = fetch(f'/holograms/mixed/{n}')
        assert '<div id="app"></div>' in child.body.decode() and _parse(child).words < 200
        bodies.append(child.body)
    assert len(set(bodies)) == 3
    assert fetch('/holograms/mixed/4').status == 404
    tags = {c.name: c.tags for c in cases() if c.family == 'holograms'}
    assert tags['script-links'] == tags['mixed'] == ('own source', 'production only')
