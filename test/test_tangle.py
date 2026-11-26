import re
from datetime import datetime, timezone

from afm_pathological import assets
from afm_pathological.catalog import cases
from afm_pathological.model import Request
from afm_pathological.site import respond

HOST = 'breadcrumbs.pathological.answersfrom.me'


def _links(response) -> list[str]:
    """The href of each <a> element of a response body, in order."""
    return [href for href in re.findall(r'<a [^>]*?href="([^"]*)"', response.body.decode())]


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def _get(path: str, query: str = ''):
    """One GET to the site with a query string."""
    return respond(Request(host=HOST, path=path, query=query))


def _article(fetch, path: str, links: list[str] | None = None):
    """Assert that a path is an article page, with the given links when they are given."""
    response = fetch(path)
    assert response.status == 200, path
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    assert _words(response) >= 250, path
    if links is not None:
        assert _links(response) == links, path
    return response


def test_section_links_every_case_except_own_source(fetch):
    """/tangle/ is an article with the links of the cases; the 150 links page is its own source."""
    response = _article(fetch, '/tangle/')
    links = _links(response)
    assert '/tangle/broken' in links and '/tangle/deep/1' in links and '/tangle/list' in links
    assert '/tangle/many/' not in links
    assert all(fetch(link).status == 200 for link in links)


def test_broken_link_and_missing(fetch):
    """broken links to /tangle/missing, which has no case and answers 404."""
    _article(fetch, '/tangle/broken', ['/tangle/missing'])
    assert fetch('/tangle/missing').status == 404


def test_loop(fetch):
    """A links to B, B links to A and self links to itself."""
    _article(fetch, '/tangle/loop-a', ['/tangle/loop-b'])
    _article(fetch, '/tangle/loop-b', ['/tangle/loop-a'])
    _article(fetch, '/tangle/self', ['/tangle/self'])


def test_deep_chain(fetch):
    """Each of /tangle/deep/1 to 3 links to the next; 4 links to nothing; 5 is 404."""
    for n in range(1, 4):
        _article(fetch, f'/tangle/deep/{n}', [f'/tangle/deep/{n + 1}'])
    _article(fetch, '/tangle/deep/4', [])
    assert fetch('/tangle/deep/5').status == 404


def test_too_many_links(fetch):
    """/tangle/many/ links to 150 article pages."""
    response = _article(fetch, '/tangle/many/', [f'/tangle/many/{n}' for n in range(1, 151)])
    assert response.status == 200
    for n in (1, 75, 150):
        _article(fetch, f'/tangle/many/{n}', [])
    assert fetch('/tangle/many/0').status == 404
    assert fetch('/tangle/many/151').status == 404
    assert fetch('/tangle/many/x').status == 404


def test_other_test_host_and_external(fetch):
    """other-host links to the librarian host of the request host; external links to example.com."""
    _article(fetch, '/tangle/other-host', ['https://librarian.pathological.answersfrom.me/articles/starter'])
    local = fetch('/tangle/other-host', host='Breadcrumbs.Test.Local')
    assert _links(local) == ['https://librarian.test.local/articles/starter']
    _article(fetch, '/tangle/external', ['https://example.com/'])


def test_not_a_page(fetch):
    """not-a-page has mailto:, tel: and javascript: links, each with anchor text."""
    response = _article(fetch, '/tangle/not-a-page')
    links = _links(response)
    assert [link.split(':')[0] for link in links] == ['mailto', 'tel', 'javascript']
    assert all(re.search(rf'<a href="{re.escape(link)}">[^<]+</a>', response.body.decode()) for link in links)


def test_wrong_scheme(fetch):
    """schemes has http://, HTTP:// and webcal:// links to the request host; plain-http is an article."""
    host = 'breadcrumbs.pathological.answersfrom.me'
    _article(fetch, '/tangle/schemes', [f'{s}://{host}/tangle/plain-http' for s in ('http', 'HTTP', 'webcal')])
    _article(fetch, '/tangle/plain-http', [])


def test_fragment(fetch):
    """fragment links to #part, to the target and to the target with #part."""
    _article(fetch, '/tangle/fragment', ['#part', '/tangle/fragment-target', '/tangle/fragment-target#part'])
    _article(fetch, '/tangle/fragment-target', [])


def test_relative(fetch):
    """relative/page has sibling and ../up; based/page has a <base> and child; the targets are articles."""
    _article(fetch, '/tangle/relative/page', ['sibling', '../up'])
    response = _article(fetch, '/tangle/based/page', ['child'])
    assert '<base href="/tangle/base-dir/">' in response.body.decode().split('</head>')[0]
    for path in ('/tangle/relative/sibling', '/tangle/up', '/tangle/base-dir/child'):
        _article(fetch, path, [])
    assert fetch('/tangle/sibling').status == 404


def test_tracking(fetch):
    """tracking links to the tracked page with utm_source, with lang and with no query; tracked ignores the query."""
    links = ['/tangle/tracked?utm_source=x', '/tangle/tracked?lang=en-us', '/tangle/tracked']
    _article(fetch, '/tangle/tracking', links)
    assert fetch('/tangle/tracked').body == fetch('/tangle/tracked').body
    assert _words(_article(fetch, '/tangle/tracked', [])) >= 250


def test_pagination(fetch):
    """list shows page 1 by default and for page=1, and pages 2 and 3 with their own articles."""
    first = _article(fetch, '/tangle/list', ['/tangle/list/a1', '/tangle/list/a2', '/tangle/list?page=2',
                                             '/tangle/list?page=3'])
    assert fetch('/tangle/list').body == first.body
    one, two, three = (_get('/tangle/list', f'page={n}') for n in (1, 2, 3))
    assert one.body == first.body
    assert _links(two) == ['/tangle/list/b1', '/tangle/list/b2']
    assert _links(three) == ['/tangle/list/c1', '/tangle/list/c2']
    assert len({one.body, two.body, three.body}) == 3
    for item in ('a1', 'a2', 'b1', 'b2', 'c1', 'c2'):
        _article(fetch, f'/tangle/list/{item}', [])
    assert fetch('/tangle/list/d1').status == 404


def test_files(fetch):
    """files links to the four files; each is served with its content type and a valid body."""
    names = ('paper.pdf', 'talk.mp3', 'photo.jpg', 'styles.css')
    _article(fetch, '/tangle/files', [f'/tangle/files/{n}' for n in names])
    for name, content_type in (('paper.pdf', 'application/pdf'), ('talk.mp3', 'audio/mpeg'),
                               ('photo.jpg', 'image/jpeg'), ('styles.css', 'text/css')):
        response = fetch(f'/tangle/files/{name}')
        assert response.status == 200 and response.headers['content-type'].startswith(content_type), name
        assert response.body
    assert fetch('/tangle/files/other.pdf').status == 404
    assert fetch('/tangle/files/paper.pdf').body == assets.pdf_bytes('Sourdough baking notes')


def test_pdf_asset():
    """The PDF starts with %PDF, ends with %%EOF, and each xref offset points at its object."""
    pdf = assets.pdf_bytes('A line (with) parens')
    assert pdf.startswith(b'%PDF') and pdf.rstrip().endswith(b'%%EOF')
    assert b'(A line \\(with\\) parens) Tj' in pdf
    xref = int(re.search(rb'startxref\n(\d+)', pdf).group(1))
    assert pdf[xref:].startswith(b'xref')
    offsets = [int(m) for m in re.findall(rb'(\d{10}) 00000 n', pdf)]
    assert len(offsets) == 5
    for number, offset in enumerate(offsets, 1):
        assert pdf[offset:].startswith(f'{number} 0 obj'.encode())
    length = int(re.search(rb'/Length (\d+)', pdf).group(1))
    start = pdf.index(b'stream\n') + 7
    assert pdf[start + length:].startswith(b'\nendstream')


def test_mp3_asset():
    """The MP3 is 38 or more frames of MPEG-1 Layer III, each starting with the sync 0xFF 0xFB."""
    mp3 = assets.mp3_bytes()
    assert mp3[:2] == b'\xff\xfb'
    assert len(mp3) % 417 == 0 and len(mp3) // 417 >= 38
    assert all(mp3[i:i + 2] == b'\xff\xfb' for i in range(0, len(mp3), 417))


def test_jpeg_asset():
    """The JPEG starts with 0xFF 0xD8 and ends with 0xFF 0xD9; its frame header says 1x1."""
    jpeg = assets.jpeg_bytes()
    assert jpeg[:2] == b'\xff\xd8' and jpeg[-2:] == b'\xff\xd9'
    frame = re.search(rb'\xff[\xc0\xc2]\x00.\x08(....)', jpeg, re.DOTALL)
    assert frame.group(1) == b'\x00\x01\x00\x01'


def test_bracket_host(fetch):
    """The link http://[cnn-embed-123] comes before the link to after-bracket."""
    _article(fetch, '/tangle/bracket', ['http://[cnn-embed-123]', '/tangle/after-bracket'])
    _article(fetch, '/tangle/after-bracket', [])


def test_nofollow(fetch):
    """nofollow has one link with rel="nofollow"."""
    response = _article(fetch, '/tangle/nofollow', ['/tangle/nofollow-target'])
    assert 'rel="nofollow"' in response.body.decode()
    _article(fetch, '/tangle/nofollow-target', [])


def test_image_link(fetch):
    """The only content of the link is an <img>."""
    response = _article(fetch, '/tangle/image-link', ['/tangle/image-target'])
    assert '<a href="/tangle/image-target"><img src="/tangle/files/photo.jpg" alt=""></a>' in response.body.decode()
    _article(fetch, '/tangle/image-target', [])


def test_odd_urls(fetch):
    """odd links to a 2,090 character segment, to the percent-encoded and to the plain café; both answer the same."""
    long_path = '/tangle/' + 'a' * 2090
    response = _article(fetch, '/tangle/odd', [long_path, '/tangle/caf%C3%A9', '/tangle/café'])
    assert len(response.body.decode().split(f'href="{long_path}"')) == 2
    _article(fetch, long_path, [])
    encoded, plain = fetch('/tangle/caf%C3%A9'), fetch('/tangle/café')
    assert encoded.status == plain.status == 200 and encoded.body == plain.body
    assert fetch('/tangle/caf%c3%a9').body == plain.body
    assert fetch('/tangle/' + 'a' * 2089).status == 404
    assert fetch('/tangle/cafe').status == 404


def test_every_path_is_a_page_or_a_file(fetch):
    """Each exact path of the tangle cases answers 200."""
    for case in cases():
        if case.family == 'tangle':
            for path in case.paths:
                if '<' not in path:
                    assert fetch(path).status == 200, path


def test_conditional_get(fetch):
    """A tangle page sends an ETag and answers a matching conditional request with 304."""
    etag = fetch('/tangle/broken').headers['etag']
    assert fetch('/tangle/broken', headers={'if-none-match': etag}).status == 304


def test_stable_over_time(fetch):
    """A tangle page does not change with the time of the request."""
    later = datetime(2026, 12, 1, 3, 4, 5, tzinfo=timezone.utc)
    assert fetch('/tangle/other-host').body == fetch('/tangle/other-host', now=later).body
