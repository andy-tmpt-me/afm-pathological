from typing import Callable, Optional, Sequence
from urllib.parse import unquote

from afm_pathological import assets
from afm_pathological.catalog import Case, section_case
from afm_pathological.content import article
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, page
from afm_pathological.responses import html

_Builder = Callable[[Request], str]
_FILES = ('paper.pdf', 'talk.mp3', 'photo.jpg', 'styles.css')
_LONG = 'a' * 2090
_ODD_KEYS = {_LONG: 'long', 'café': 'cafe'}


def _page(path: str, links: Sequence[str | tuple[str, str]] = (), raw: str = '', head: str = '') -> str:
    """An article page for a path, with the links after the text and raw HTML after the links."""
    a = article(path.strip('/').replace('/', '-'))
    return page(a.title, '\n'.join(filter(None, [article_body(a, links), raw])), head)


def _static(path: str, links: Sequence[str | tuple[str, str]] = (), raw: str = '', head: str = '') -> _Builder:
    """A builder for a page that does not depend on the request."""
    return lambda request: _page(path, links, raw, head)


def _pages(name: str, behavior: str, pages: dict[str, _Builder], tags: tuple[str, ...] = ()) -> Case:
    """A case whose paths are exact pages, each with a builder."""
    return Case('tangle', name, tuple(pages), behavior,
                lambda request: html(pages[request.path](request)) if request.path in pages else None, tags)


def _leaves(*paths: str) -> dict[str, _Builder]:
    """Article pages with no links."""
    return {path: _static(path) for path in paths}


def _other_host(request: Request) -> str:
    """A link to the librarian host that shares the domain of the request host."""
    return _page('/tangle/other-host', [request.sibling_url('librarian', '/articles/starter')])


def _schemes(request: Request) -> str:
    """Links to the plain-http page with three schemes on the request host."""
    return _page('/tangle/schemes',
                 [f'{s}://{request.host_header}/tangle/plain-http' for s in ('http', 'HTTP', 'webcal')])


def _many(request: Request) -> Optional[Response]:
    """/tangle/many/ with 150 links, and each of its 150 pages."""
    number = request.path.removeprefix('/tangle/many/')
    if not number:
        return html(_page(request.path, [f'/tangle/many/{n}' for n in range(1, 151)]))
    return html(_page(request.path)) if number in {str(n) for n in range(1, 151)} else None


def _list(request: Request) -> Optional[Response]:
    """/tangle/list: page 1 by default, ?page=2 and ?page=3 list other articles; and the six articles."""
    if request.path != '/tangle/list':
        return html(_page(request.path))
    n = {'page=2': 2, 'page=3': 3}.get(request.query, 1)
    if n == 1:
        return html(_page(request.path, ['/tangle/list/a1', '/tangle/list/a2', '/tangle/list?page=2',
                                         '/tangle/list?page=3']))
    letter = 'abc'[n - 1]
    return html(_page(f'/tangle/list/page-{n}', [f'/tangle/list/{letter}1', f'/tangle/list/{letter}2']))


def _files(request: Request) -> Optional[Response]:
    """The page that links to the four files, and each file."""
    kinds = {'paper.pdf': ('application/pdf', lambda: assets.pdf_bytes('Sourdough baking notes')),
             'talk.mp3': ('audio/mpeg', assets.mp3_bytes), 'photo.jpg': ('image/jpeg', assets.jpeg_bytes),
             'styles.css': ('text/css', lambda: b'body { font-family: serif; }\n')}
    name = request.path.removeprefix('/tangle/files')
    if not name:
        return html(_page(request.path, [f'/tangle/files/{n}' for n in _FILES]))
    if name.removeprefix('/') not in kinds:
        return None
    content_type, build = kinds[name.removeprefix('/')]
    return Response(200, {'content-type': content_type}, build())


def _odd(request: Request) -> Optional[Response]:
    """The page with the odd links, and the pages with a long or a non-ASCII name."""
    name = request.path.removeprefix('/tangle/')
    if name == 'odd':
        return html(_page(request.path, [f'/tangle/{_LONG}', '/tangle/caf%C3%A9', '/tangle/café']))
    key = _ODD_KEYS.get(unquote(name))
    return html(_page(f'/tangle/odd-{key}')) if key else None


_NOFOLLOW = ('<ul>\n<li><a href="/tangle/nofollow-target" rel="nofollow">A page that crawlers should not follow</a>'
             '</li>\n</ul>')
_IMAGE = '<div><a href="/tangle/image-target"><img src="/tangle/files/photo.jpg" alt=""></a></div>'

_SECTION = section_case('tangle', 'Tangled links of sourdough baking', [
    '/tangle/broken', '/tangle/loop-a', '/tangle/self', '/tangle/deep/1', '/tangle/other-host', '/tangle/external',
    '/tangle/not-a-page', '/tangle/schemes', '/tangle/fragment', '/tangle/relative/page', '/tangle/based/page',
    '/tangle/tracking', '/tangle/list', '/tangle/files', '/tangle/bracket', '/tangle/nofollow',
    '/tangle/image-link', '/tangle/odd'])

CASES: list[Case] = [
    _SECTION,
    _pages('broken-link', 'A link to /tangle/missing, which answers 404', {
        '/tangle/broken': _static('/tangle/broken', ['/tangle/missing'])}),
    _pages('loop', 'A links to B and B links to A; self links to itself', {
        '/tangle/loop-a': _static('/tangle/loop-a', ['/tangle/loop-b']),
        '/tangle/loop-b': _static('/tangle/loop-b', ['/tangle/loop-a']),
        '/tangle/self': _static('/tangle/self', ['/tangle/self'])}),
    _pages('deep-chain', 'Each page links to the next, from 1 to 4; 4 links to nothing', {
        **{f'/tangle/deep/{n}': _static(f'/tangle/deep/{n}', [f'/tangle/deep/{n + 1}']) for n in range(1, 4)},
        '/tangle/deep/4': _static('/tangle/deep/4')}),
    Case('tangle', 'too-many-links', ('/tangle/many/', '/tangle/many/<n>'),
         'A page with 150 links to 150 article pages', _many, ('own source',)),
    _pages('other-test-host', 'A link to the librarian host of the same domain', {'/tangle/other-host': _other_host}),
    _pages('external', 'A link to https://example.com/', {
        '/tangle/external': _static('/tangle/external', ['https://example.com/'])}),
    _pages('not-a-page', 'Links with mailto:, tel: and javascript:', {
        '/tangle/not-a-page': _static('/tangle/not-a-page', [('mailto:baker@example.com', 'Email the baker'),
                                                             ('tel:+15555550100', 'Call the bakery'),
                                                             ('javascript:void(0)', 'Open the recipe')])}),
    _pages('wrong-scheme', 'Links with http://, HTTP:// and webcal:// to /tangle/plain-http', {
        '/tangle/schemes': _schemes, **_leaves('/tangle/plain-http')}),
    _pages('fragment', 'Links to #part, to the target and to the target with #part', {
        '/tangle/fragment': _static('/tangle/fragment', ['#part', '/tangle/fragment-target',
                                                         '/tangle/fragment-target#part']),
        **_leaves('/tangle/fragment-target')}),
    _pages('relative', 'Links sibling and ../up; a second page has a base element and a link child', {
        '/tangle/relative/page': _static('/tangle/relative/page', ['sibling', '../up']),
        '/tangle/based/page': _static('/tangle/based/page', ['child'], head='<base href="/tangle/base-dir/">'),
        **_leaves('/tangle/relative/sibling', '/tangle/up', '/tangle/base-dir/child')}),
    _pages('tracking', 'Links to the tracked page with utm_source, with lang and with no query', {
        '/tangle/tracking': _static('/tangle/tracking', ['/tangle/tracked?utm_source=x', '/tangle/tracked?lang=en-us',
                                                         '/tangle/tracked']),
        **_leaves('/tangle/tracked')}),
    Case('tangle', 'pagination', ('/tangle/list', *(f'/tangle/list/{c}{n}' for c in 'abc' for n in (1, 2))),
         'Links to ?page=2 and ?page=3; each page of the list has other articles', _list),
    Case('tangle', 'files', ('/tangle/files', *(f'/tangle/files/{n}' for n in _FILES)),
         'Links to a PDF, an MP3, a JPEG and a CSS file', _files),
    _pages('bracket-host', 'A link to http://[cnn-embed-123], then a link to /tangle/after-bracket', {
        '/tangle/bracket': _static('/tangle/bracket', ['http://[cnn-embed-123]', '/tangle/after-bracket']),
        **_leaves('/tangle/after-bracket')}),
    _pages('nofollow', 'A link with rel="nofollow"', {
        '/tangle/nofollow': _static('/tangle/nofollow', raw=_NOFOLLOW), **_leaves('/tangle/nofollow-target')}),
    _pages('image-link', 'A link whose only content is an image', {
        '/tangle/image-link': _static('/tangle/image-link', raw=_IMAGE), **_leaves('/tangle/image-target')}),
    Case('tangle', 'odd-urls', ('/tangle/odd', '/tangle/caf%C3%A9', '/tangle/café', '/tangle/<name>'),
         'Links to a URL of 2,100 characters (the README shows it as <name>), to /tangle/caf%C3%A9 and to '
         '/tangle/café; both forms answer with the same page', _odd),
]
