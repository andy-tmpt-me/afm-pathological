from html import escape
from typing import Callable, Optional

from afm_pathological.catalog import Case, section_case
from afm_pathological.content import article
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, article_page, page
from afm_pathological.responses import html, xml
from afm_pathological.sitemaps import urlset

_SITEMAP_PATHS = ('/articles/starter', '/articles/steam/', '/articles/steam', '/tangle/missing')


def _canonical(url: str) -> str:
    """The <head> element that names the canonical URL of a page."""
    return f'<link rel="canonical" href="{escape(url, quote=True)}">'


def _twin(key: str, title: Optional[str], variant: int) -> str:
    """One page of a pair: the article of the key in the variant, under the title of the article or a given title."""
    a = article(key, variant)
    return page(title or a.title, article_body(a))


def _pages(name: str, behavior: str, pages: dict[str, Callable[[Request], str]], tags: tuple[str, ...] = ()) -> Case:
    """A case whose paths are exact pages, each with a builder."""
    return Case('doppelgangers', name, tuple(pages), behavior,
                lambda request: html(pages[request.path](request)) if request.path in pages else None, tags)


def _print(request: Request) -> str:
    """The page that links to itself and to its print version."""
    return article_page('doppelgangers-print', ['/doppelgangers/print', '/doppelgangers/print?print=1'])


def _sitemap(request: Request) -> Response:
    """A sitemap with a name that is not sitemap.xml."""
    return xml(urlset([(request.url(path), None) for path in _SITEMAP_PATHS]))


_SECTION = section_case('doppelgangers', 'Doppelgangers: one sourdough page at more than one URL', [
    '/doppelgangers/slash', '/doppelgangers/slash/', '/doppelgangers/slash/index.html', '/doppelgangers/strict/',
    '/doppelgangers/canon-a', '/doppelgangers/canon-b', '/doppelgangers/canon-other', '/doppelgangers/canon-host',
    '/doppelgangers/twin-a', '/doppelgangers/twin-b', '/doppelgangers/tw-a', '/doppelgangers/tw-b',
    '/doppelgangers/print'])

CASES: list[Case] = [
    _SECTION,
    _pages('slash-forms', 'The same page at slash, slash/ and slash/index.html', {
        path: lambda request: article_page('doppelgangers-slash')
        for path in ('/doppelgangers/slash', '/doppelgangers/slash/', '/doppelgangers/slash/index.html')}),
    _pages('strict-slash', 'strict/ answers 200 and strict answers 404', {
        '/doppelgangers/strict/': lambda request: article_page('doppelgangers-strict')}),
    _pages('same-canonical', 'Two pages with different texts and the canonical URL of canon-a', {
        f'/doppelgangers/canon-{x}': lambda request, x=x: article_page(
            f'doppelgangers-canon-{x}', head_html=_canonical(request.url('/doppelgangers/canon-a'))) for x in 'ab'}),
    _pages('canonical-elsewhere',
           'canon-other names /articles/starter as canonical; canon-host names the librarian host',
           {'/doppelgangers/canon-other': lambda request: article_page(
               'doppelgangers-canon-other', head_html=_canonical(request.url('/articles/starter'))),
            '/doppelgangers/canon-host': lambda request: article_page(
                'doppelgangers-canon-host',
                head_html=_canonical(request.sibling_url('librarian', '/articles/starter')))}),
    _pages('same-text',
           'Twins with the same title and texts that differ in one sentence; the tw pair has a title of 8 characters',
           {'/doppelgangers/twin-a': lambda request: _twin('doppelgangers-twin', None, 0),
            '/doppelgangers/twin-b': lambda request: _twin('doppelgangers-twin', None, 1),
            '/doppelgangers/tw-a': lambda request: _twin('doppelgangers-tw', 'Tw pages', 0),
            '/doppelgangers/tw-b': lambda request: _twin('doppelgangers-tw', 'Tw pages', 1)}),
    Case('doppelgangers', 'sitemap-and-visit', ('/doppelgangers/post-sitemap.xml',),
         'A sitemap that is not sitemap.xml: /articles/starter, /articles/steam/, /articles/steam and /tangle/missing',
         _sitemap, ('own source',)),
    _pages('print-version', 'A page that links to itself and to itself with ?print=1; both give the same page', {
        '/doppelgangers/print': _print}),
]
