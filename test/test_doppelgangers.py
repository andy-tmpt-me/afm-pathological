import re
from html import unescape

from afm_pathological.model import Request
from afm_pathological.site import respond

HOST = 'breadcrumbs.pathological.answersfrom.me'


def _links(response) -> list[str]:
    """The href of each <a> element of a response body, in order."""
    return [unescape(href) for href in re.findall(r'<a href="([^"]*)"', response.body.decode())]


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def _title(response) -> str:
    """The <title> of a response body."""
    return re.search(r'<title>(.*?)</title>', response.body.decode()).group(1)


def _text(response) -> str:
    """The text of the <p> elements of a response body."""
    return ' '.join(re.findall(r'<p>(.*?)</p>', response.body.decode()))


def _canonical(response) -> str:
    """The href of the canonical link in the <head> of a response body."""
    return re.search(r'<link rel="canonical" href="([^"]*)">', response.body.decode().split('</head>')[0]).group(1)


def test_section_links(fetch):
    """/doppelgangers/ is an article that links to each case page except the own-source sitemap."""
    response = fetch('/doppelgangers/')
    assert response.status == 200 and _words(response) >= 250
    links = _links(response)
    assert links[:4] == ['/doppelgangers/slash', '/doppelgangers/slash/', '/doppelgangers/slash/index.html',
                         '/doppelgangers/strict/']
    assert '/doppelgangers/post-sitemap.xml' not in links
    assert all(fetch(link).status == 200 for link in links)


def test_slash_forms(fetch):
    """slash, slash/ and slash/index.html return the same body."""
    bodies = {fetch(p).body for p in ('/doppelgangers/slash', '/doppelgangers/slash/',
                                      '/doppelgangers/slash/index.html')}
    assert len(bodies) == 1 and _words(fetch('/doppelgangers/slash')) >= 250


def test_strict_slash(fetch):
    """strict/ answers 200 and strict answers 404."""
    assert fetch('/doppelgangers/strict/').status == 200
    assert fetch('/doppelgangers/strict').status == 404


def test_same_canonical(fetch):
    """canon-a and canon-b name the absolute URL of canon-a and have different texts."""
    a, b = fetch('/doppelgangers/canon-a'), fetch('/doppelgangers/canon-b')
    url = f'https://{HOST}/doppelgangers/canon-a'
    assert _canonical(a) == _canonical(b) == url
    assert _text(a) != _text(b) and _title(a) != _title(b)
    assert _words(a) >= 250 and _words(b) >= 250 and _links(a) == _links(b) == []


def test_canonical_elsewhere(fetch):
    """canon-other names /articles/starter; canon-host names the librarian host of the request host."""
    assert _canonical(fetch('/doppelgangers/canon-other')) == f'https://{HOST}/articles/starter'
    host = _canonical(fetch('/doppelgangers/canon-host'))
    assert host == 'https://librarian.pathological.answersfrom.me/articles/starter'
    other = fetch('/doppelgangers/canon-host', host='Breadcrumbs.Test.Local')
    assert _canonical(other) == 'https://librarian.test.local/articles/starter'


def _differing(a: str, b: str) -> int:
    """The number of characters in the longer text that are outside the common prefix and suffix."""
    prefix = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    suffix = next((i for i, (x, y) in enumerate(zip(a[::-1], b[::-1])) if x != y), 0)
    return max(len(a), len(b)) - prefix - suffix


def test_same_text(fetch):
    """Twins have the same title and texts that differ in under 10% of the characters; tw has a short title."""
    for first, second, title_length in (('twin-a', 'twin-b', None), ('tw-a', 'tw-b', 8)):
        a, b = fetch(f'/doppelgangers/{first}'), fetch(f'/doppelgangers/{second}')
        assert _title(a) == _title(b)
        assert len(_title(a)) == title_length if title_length else len(_title(a)) > 10
        assert _text(a) != _text(b)
        assert _differing(_text(a), _text(b)) < 0.1 * len(_text(a))
        assert _words(a) >= 250 and _words(b) >= 250
    assert _title(fetch('/doppelgangers/twin-a')) != _title(fetch('/doppelgangers/tw-a'))


def test_sitemap(fetch):
    """post-sitemap.xml lists the four absolute URLs of the spec."""
    response = fetch('/doppelgangers/post-sitemap.xml')
    assert response.status == 200 and response.headers['content-type'] == 'application/xml'
    assert re.findall(r'<loc>(.*?)</loc>', response.body.decode()) == [
        f'https://{HOST}{path}' for path in ('/articles/starter', '/articles/steam/', '/articles/steam',
                                             '/tangle/missing')]


def test_print_version(fetch):
    """print links to itself and to ?print=1; both answer with the same article."""
    plain = fetch('/doppelgangers/print')
    assert _links(plain) == ['/doppelgangers/print', '/doppelgangers/print?print=1']
    printed = respond(Request(host=HOST, path='/doppelgangers/print', query='print=1'))
    assert printed.status == 200 and printed.body == plain.body


def test_pages_are_unique_articles(fetch):
    """Every exact case page has an article of 250 words and its own title, except the twins."""
    names = ('slash', 'strict/', 'canon-a', 'canon-b', 'canon-other', 'canon-host', 'print')
    titles = {_title(fetch(f'/doppelgangers/{n}')) for n in names}
    assert len(titles) == 7
