from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional

from afm_pathological.catalog import Case
from afm_pathological.clock import EPOCH, day_number, http_date, parse_date, today
from afm_pathological.content import article
from afm_pathological.feedgen import Entry, atom, rss
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, article_page
from afm_pathological.responses import html, text, xml

RSS_TYPE = 'application/rss+xml'
ATOM_TYPE = 'application/atom+xml'
LONG_DAYS = 800  # a /feeds/long/<date> page exists from this many days before the date in effect


def at_six(day: date) -> datetime:
    """06:00 UTC of a date, the time of each feed entry."""
    return datetime.combine(day, time(6), timezone.utc)


def recent_dates(request: Request, count: int, floor: Optional[date] = EPOCH) -> list[date]:
    """The date in effect and the dates before it, newest first, none before the floor."""
    days = (today(request) - timedelta(days=i) for i in range(count))
    return [day for day in days if floor is None or day >= floor]


def daily_entry(request: Request, day: date, dated: bool = True, date_of: date | None = None) -> Entry:
    """The entry of a daily page; the date is 06:00 UTC of date_of, by default of the page date."""
    a = article(f'daily-{day}')
    return Entry(a.title, request.url(f'/daily/{day}'), at_six(date_of or day) if dated else None, a.paragraphs[0])


def daily_entries(request: Request) -> list[Entry]:
    """The entries of the last 10 daily pages, newest first."""
    return [daily_entry(request, day) for day in recent_dates(request, 10)]


def _title(request: Request) -> str:
    """The title of each feed."""
    return f'Sourdough dispatches from {request.host_header}'


def _feed_response(request: Request, body: str, content_type: str, dated: bool) -> Response:
    """A feed whose Last-Modified is the date in effect; a feed with no dates sends no validators at all."""
    response = xml(body, content_type)
    if dated:
        response.headers['last-modified'] = http_date(today(request))
    else:
        response.validators = False
    return response


def _newest(entries: list[Entry]) -> Optional[datetime]:
    """The newest date of the entries, or None."""
    return max((e.date for e in entries if e.date), default=None)


def rss_response(request: Request, entries: list[Entry], dated: bool = True) -> Response:
    """An RSS feed whose lastBuildDate is the date of the newest entry, if it has dates."""
    rss_body = rss(_title(request), request.url('/'), entries, _newest(entries) if dated else None)
    return _feed_response(request, rss_body, RSS_TYPE, dated)


def daily_rss(request: Request) -> Response:
    """The daily feed as RSS."""
    return rss_response(request, daily_entries(request))


def _atom(request: Request) -> Response:
    """The daily feed as Atom."""
    entries = daily_entries(request)
    return _feed_response(request, atom(_title(request), request.url('/'), entries, _newest(entries)), ATOM_TYPE, True)


def _backdated(request: Request) -> Response:
    """The daily entries, each dated 2026-01-01 06:00 UTC; no feed-level date."""
    entries = [daily_entry(request, day, date_of=EPOCH) for day in recent_dates(request, 10)]
    return rss_response(request, entries, dated=False)


def _edited(request: Request) -> Response:
    """The daily feed and, last, the honest-edit page with the date in effect."""
    edit = Entry(article('chameleons-honest-edit').title, request.url('/chameleons/honest-edit'),
                 at_six(today(request)), 'A page whose text changes each day.')
    return rss_response(request, [*daily_entries(request), edit])


def _undated(request: Request) -> Response:
    """The daily entries with no dates at all."""
    entries = [daily_entry(request, day, dated=False) for day in recent_dates(request, 10)]
    return rss_response(request, entries, dated=False)


def _long(request: Request) -> Optional[Response]:
    """600 entries that link to /feeds/long/<date> pages, newest first; the second feed has them oldest first."""
    if request.path.startswith('/feeds/long/'):
        day = parse_date(request.path.removeprefix('/feeds/long/'))
        valid = day is not None and 0 <= (today(request) - day).days <= LONG_DAYS
        return html(article_page(f'feeds-long-{day}')) if valid else None
    entries = []
    for day in recent_dates(request, 600, floor=None):
        a = article(f'feeds-long-{day}')
        entries.append(Entry(a.title, request.url(f'/feeds/long/{day}'), at_six(day), a.paragraphs[0]))
    return rss_response(request, entries if request.path == '/feeds/long.xml' else entries[::-1])


def _full_text(request: Request) -> Response:
    """The daily entries with the article as HTML in content:encoded; the first description has 2,500 characters."""
    entries = []
    for i, day in enumerate(recent_dates(request, 10)):
        a = article(f'daily-{day}')
        description = (' '.join(a.paragraphs) * 3)[:2500] if i == 0 else a.paragraphs[0][:200]
        entries.append(Entry(a.title, request.url(f'/daily/{day}'), at_six(day), description, article_body(a)))
    return rss_response(request, entries)


def _odd(request: Request) -> Response:
    """A guid-only entry, two entries with one link, a relative link and an entry with no title."""
    days = recent_dates(request, 4, floor=None)
    same, relative, untitled = (daily_entry(request, day) for day in days[:3])
    entries = [Entry(guid='urn:pathological:guid-only', description='An entry that has only a guid.'),
               same, Entry(f'{same.title} (copy)', same.link, same.date, same.description),
               Entry(relative.title, f'/daily/{days[1]}', relative.date, relative.description),
               Entry('', untitled.link, untitled.date, untitled.description)]
    return rss_response(request, entries)


def _outage(request: Request) -> Response:
    """The daily feed on an even day number; 503 on an odd one."""
    return daily_rss(request) if day_number(request) % 2 == 0 else text('Service unavailable.\n', status=503)


def _feed_case(name: str, path: str, behavior: str, handler: Callable[[Request], Optional[Response]],
               tags: tuple[str, ...] = ()) -> Case:
    """A case of the feeds family that serves one path."""
    return Case('feeds', name, (path,), behavior, handler, tags)


CASES: list[Case] = [
    _feed_case('formats', '/feeds/atom.xml', 'The daily feed as Atom: the last 10 daily pages, newest first, each '
               'dated 06:00 UTC; `updated` is the date of the newest entry', _atom, ('first',)),
    _feed_case('backdated-entry', '/feeds/backdated.xml', 'The last 10 daily pages, newest first, each dated '
               '2026-01-01 06:00 UTC; no feed-level date. Each day a new URL enters and no date is newer than '
               'before', _backdated),
    _feed_case('edited-entry', '/feeds/edited.xml', 'The daily feed and, last, `/chameleons/honest-edit` with the '
               'date of the day', _edited),
    _feed_case('no-dates', '/feeds/undated.xml', 'The daily entries with no date, in a feed with no date', _undated),
    Case('feeds', 'long-feed', ('/feeds/long.xml', '/feeds/long-oldest-first.xml', '/feeds/long/<date>'),
         '600 entries, newest first, each a link to `/feeds/long/<date>`; the second feed has the reverse order. A '
         'long page exists for each date from 800 days before the date in effect up to that date', _long),
    _feed_case('full-text', '/feeds/full-text.xml', 'Short descriptions (one of 2,500 characters) and the article as '
               'HTML in `content:encoded`', _full_text),
    _feed_case('odd-entries', '/feeds/odd.xml', 'An entry with only a guid, two entries with the same link, an '
               'entry with a relative link and an entry with no title', _odd),
    _feed_case('oracle-outage', '/feeds/outage.xml', 'The daily feed when N is even, 503 when N is odd', _outage,
               ('first',)),
]
