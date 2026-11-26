from typing import Optional

from afm_pathological.catalog import Case, section_case
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_page, page
from afm_pathological.responses import html, redirect

CHAIN = {'/detours/chain/1': (301, '/detours/chain/2'), '/detours/chain/2': (302, '/detours/chain/3'),
         '/detours/chain/3': (307, '/detours/landed-2')}
LOOP = {'/detours/loop-a': '/detours/loop-b', '/detours/loop-b': '/detours/loop-a'}
REFRESH = '<meta http-equiv="refresh" content="0; url=/detours/refreshed">'


def _article(request: Request) -> Response:
    """The article of a target page."""
    return html(article_page(request.path.removeprefix('/detours/')))


def _chain(request: Request) -> Optional[Response]:
    """The three hops of the chain, then the landing page."""
    if request.path == '/detours/landed-2':
        return _article(request)
    status, location = CHAIN[request.path]
    return redirect(location, status)


def _emigrant(request: Request) -> Response:
    """301 to librarian on the rest of the request host."""
    return redirect(request.sibling_url('librarian', '/articles/starter'))


def _refresh(request: Request) -> Response:
    """The page of the meta refresh, or its target."""
    if request.path == '/detours/refreshed':
        return _article(request)
    return html(page('Redirecting', '<p>Redirecting</p>', REFRESH))


CASES: list[Case] = [
    Case('detours', 'one-hop', ('/detours/hop', '/detours/landed'), '301 to /detours/landed, an article',
         lambda request: redirect('/detours/landed') if request.path == '/detours/hop' else _article(request)),
    Case('detours', 'chain', (*CHAIN, '/detours/landed-2'), '301 to chain/2, 302 to chain/3, 307 to /detours/landed-2',
         _chain),
    Case('detours', 'redirect-loop', tuple(LOOP), '302 to the other page of the pair, for ever',
         lambda request: redirect(LOOP[request.path], 302)),
    Case('detours', 'other-host', ('/detours/emigrant',), '301 to an article on the librarian host', _emigrant),
    Case('detours', 'meta-refresh', ('/detours/refresh', '/detours/refreshed'),
         '200 with the text Redirecting and a meta refresh element that points to /detours/refreshed', _refresh),
    section_case('detours', 'Detours: sourdough pages that send you elsewhere', [
        '/detours/hop', '/detours/chain/1', '/detours/loop-a', '/detours/emigrant', '/detours/refresh']),
]
