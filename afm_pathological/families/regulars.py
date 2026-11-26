from datetime import date, timedelta
from typing import Optional, Sequence

from afm_pathological.catalog import Case
from afm_pathological.clock import EPOCH, http_date, parse_date, today
from afm_pathological.content import article
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, article_page, page
from afm_pathological.responses import html

ARTICLES = ('starter', 'hydration', 'scoring', 'steam', 'crumb')
NOTES = ('flour', 'salt')
ARTICLE_LINKS = tuple(f'/articles/{name}' for name in ARTICLES)
NOTES_LINKS = ('/articles/steam', '/articles/crumb', *(f'/notes/{name}' for name in NOTES))


def daily_dates(request: Request) -> list[date]:
    """The date in effect and the six dates before it, newest first."""
    return [today(request) - timedelta(days=i) for i in range(7)]


def _section(key: str, title: str, links: Sequence[str]) -> Response:
    """A section page: the article of the key under the title, followed by the links."""
    return html(page(title, article_body(article(key), links)))


def _article(request: Request) -> Optional[Response]:
    """/articles/<name>: one of the five articles or the unlisted one."""
    name = request.path.removeprefix('/articles/')
    if name not in ARTICLES and name != 'unlisted':
        return None
    return html(article_page(name, ['/articles/unlisted'] if name == 'crumb' else []))


HOARD_PAGES = 500


def _hoard(request: Request) -> Optional[Response]:
    """/hoard/<n>: a constant article for each n from 1 to HOARD_PAGES."""
    n = request.path.removeprefix('/hoard/')
    valid = n.isascii() and n.isdigit() and str(int(n)) == n and 1 <= int(n) <= HOARD_PAGES
    return html(article_page(f'hoard-{n}')) if valid else None


def _daily_section(request: Request) -> Response:
    """/daily/: links to the last seven daily pages; it changes on the date in effect."""
    response = _section('daily', 'A daily journal of sourdough bakes', [f'/daily/{d}' for d in daily_dates(request)])
    response.headers['last-modified'] = http_date(today(request))
    return response


def _daily(request: Request) -> Optional[Response]:
    """/daily/<date>: a constant article for each date from 2026-01-01 to the date in effect."""
    day = parse_date(request.path.removeprefix('/daily/'))
    if day is None or not EPOCH <= day <= today(request):
        return None
    return html(article_page(f'daily-{day}'), headers={'last-modified': http_date(day)})


CASES: list[Case] = [
    Case('regulars', 'articles', ('/articles/',), 'Section page: links to the five articles',
         lambda request: _section('articles', 'Articles on sourdough baking', ARTICLE_LINKS)),
    Case('regulars', 'article', ('/articles/<name>',),
         'A constant article: starter, hydration, scoring, steam, crumb (links to unlisted) and unlisted', _article),
    Case('regulars', 'notes', ('/notes/',), 'Section page: links to two articles and the two notes',
         lambda request: _section('notes', 'Short notes from the sourdough kitchen', NOTES_LINKS)),
    Case('regulars', 'note', tuple(f'/notes/{name}' for name in NOTES), 'A constant article',
         lambda request: html(article_page(request.path.removeprefix('/notes/')))),
    Case('regulars', 'hoard', ('/hoard/<n>',),
         f'A constant article for each n from 1 to {HOARD_PAGES}, listed by `hoarder`', _hoard),
    Case('regulars', 'daily', ('/daily/',), 'Section page: links to the daily pages of the date and the six before it',
         _daily_section),
    Case('regulars', 'daily-page', ('/daily/<date>',),
         'A constant article for each date; 404 after the date in effect or before 2026-01-01', _daily),
]
