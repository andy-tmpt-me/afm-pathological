import hashlib
import re
from datetime import date
from typing import Optional

from afm_pathological.catalog import Case
from afm_pathological.clock import today
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_page
from afm_pathological.responses import html

MAX_STEPS = 24  # a link space stops after 24 steps
_MONTH = re.compile(r'(\d{4})-(0[1-9]|1[0-2])')
_COLORS, _SIZES, _SORTS = ('red', 'blue'), ('s', 'm'), ('new', 'old')


def _month_path(index: int) -> str:
    """The calendar path of a month, given as year * 12 + month - 1."""
    return f'/labyrinth/calendar/{index // 12:04d}-{index % 12 + 1:02d}'


def _month_index(day: date) -> int:
    """year * 12 + month - 1 of a date."""
    return day.year * 12 + day.month - 1


def _calendar(request: Request) -> Optional[Response]:
    """The start page, which links to the current month, and each month within 24 months of it."""
    name = request.path.removeprefix('/labyrinth/calendar/')
    current = _month_index(today(request))
    if not name:
        return html(article_page('labyrinth-calendar', [_month_path(current)]))
    match = _MONTH.fullmatch(name)
    if not match:
        return None
    index = int(match.group(1)) * 12 + int(match.group(2)) - 1
    if abs(index - current) > MAX_STEPS:
        return None
    return html(article_page(f'labyrinth-calendar-{name}', [_month_path(index - 1), _month_path(index + 1)]))


def _token(request: Request, number: int) -> str:
    """A path segment from a hash of the time of the request and the link number."""
    return hashlib.sha256(f'{request.now.isoformat()}:{number}'.encode()).hexdigest()[:12]


def _session(request: Request) -> Optional[Response]:
    """A page with the same article and five links that each add a new token to the path; at most 24 tokens deep."""
    rest = request.path.removeprefix('/labyrinth/session/')
    tokens = rest.split('/')[:-1]
    if (rest and not rest.endswith('/')) or '' in tokens or len(tokens) > MAX_STEPS:
        return None
    return html(article_page('labyrinth-session', [f'{request.path}{_token(request, n)}/' for n in range(1, 6)]))


def _shop(request: Request) -> Response:
    """The same page for each query, with links for each combination of color, size and sort."""
    return html(article_page('labyrinth-shop', [f'/labyrinth/shop?color={c}&size={s}&sort={o}'
                                                for c in _COLORS for s in _SIZES for o in _SORTS]))


CASES: list[Case] = [
    Case('labyrinth', 'calendar', ('/labyrinth/calendar/', '/labyrinth/calendar/<month>'),
         'Links to the page of the current month; each month page links to the month before and after, '
         'and a month more than 24 months away answers 404', _calendar, ('own source',)),
    Case('labyrinth', 'session-path', ('/labyrinth/session/<tokens...>',),
         '`/labyrinth/session/` and each page under it have the same title and text and five links that add a new '
         'token to the path; 24 tokens deep is the last page', _session, ('own source',)),
    Case('labyrinth', 'filters', ('/labyrinth/shop',),
         'Links that combine the query parameters color, size and sort; each query gives the same page', _shop,
         ('own source',)),
]
