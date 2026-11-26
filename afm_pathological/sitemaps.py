from datetime import date
from typing import Optional, Sequence
from xml.sax.saxutils import escape

from afm_pathological.clock import EPOCH, today
from afm_pathological.families.regulars import ARTICLE_LINKS, NOTES, daily_dates
from afm_pathological.model import Request

_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'
_NS = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def urlset(entries: Sequence[tuple[str, Optional[str]]]) -> str:
    """A <urlset> sitemap of (loc, lastmod) entries; a lastmod of None is left out."""
    urls = ''.join(f'<url><loc>{escape(loc)}</loc>' + (f'<lastmod>{lastmod}</lastmod>' if lastmod else '') + '</url>\n'
                   for loc, lastmod in entries)
    return f'{_HEAD}<urlset {_NS}>\n{urls}</urlset>\n'


def sitemap_index(locs: Sequence[str]) -> str:
    """A <sitemapindex> of sitemap URLs, with no dates."""
    items = ''.join(f'<sitemap><loc>{escape(loc)}</loc></sitemap>\n' for loc in locs)
    return f'{_HEAD}<sitemapindex {_NS}>\n{items}</sitemapindex>\n'


def regular_urls(request: Request) -> list[tuple[str, date]]:
    """The 18 absolute URLs of the regular pages that a sitemap lists, each with the date of its last change."""
    constant = ['/', '/articles/', '/notes/', '/daily/', *ARTICLE_LINKS, *(f'/notes/{n}' for n in NOTES)]
    urls = [(request.url(path), today(request) if path == '/daily/' else EPOCH) for path in constant]
    return urls + [(request.url(f'/daily/{d}'), d) for d in daily_dates(request)]
