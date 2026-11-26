import hashlib
from html import escape
from typing import Callable, Optional

from afm_pathological.catalog import Case, section_case
from afm_pathological.clock import EPOCH, day_number, http_date, parse_date, today
from afm_pathological.content import article
from afm_pathological.families.regulars import daily_dates
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, article_page, page
from afm_pathological.responses import html, not_found, redirect

SIDEBAR_TITLES = tuple(article(f'sidebar-{i}').title for i in range(10))


def _digest(request: Request) -> str:
    """A hash of the time of the request, with microseconds."""
    return hashlib.sha256(request.now.strftime('%Y-%m-%dT%H:%M:%S.%f').encode()).hexdigest()


def _plain(response: Response, **headers: str) -> Response:
    """The response with the given headers and no validators of the site."""
    response.validators = False
    response.headers.update(headers)
    return response


def _with_paragraph(key: str, extra_html: str) -> Response:
    """The article of the key with one more element after its text."""
    a = article(key)
    return html(page(a.title, article_body(a) + '\n' + extra_html))


def _honest_edit(request: Request) -> Response:
    """The text changes with N; Last-Modified is the date, and the site adds the ETag."""
    return html(article_page('honest-edit', variant=day_number(request)),
                headers={'last-modified': http_date(today(request))})


def _silent_edit(request: Request) -> Response:
    """The text changes with N; ETag and Last-Modified are constant and any conditional GET answers 304."""
    headers = {'etag': '"v1"', 'last-modified': http_date(EPOCH)}
    if 'if-none-match' in request.headers or 'if-modified-since' in request.headers:
        return _plain(Response(304, {}), **headers)
    return _plain(html(article_page('silent-edit', variant=day_number(request))), **headers)


def _restless_header(request: Request) -> Response:
    """A constant text with the time of the request as Last-Modified and no ETag."""
    return _plain(html(article_page('restless-header')), **{'last-modified': http_date(request.now)})


def _restless_markup(request: Request) -> Response:
    """A constant text with a new token in a comment and in a data attribute of <body> on each request."""
    token = _digest(request)[:16]
    body = article_page('restless-markup').replace('<body>', f'<body data-token="{token}">\n<!-- {token} -->', 1)
    return html(body)


def _sidebar(request: Request) -> Response:
    """A constant article with an <aside> of 3 of 10 titles, selected by the time of the request."""
    digest = _digest(request)
    chosen = sorted(range(10), key=lambda i: hashlib.sha256(f'{digest}:{i}'.encode()).digest())[:3]
    items = '\n'.join(f'<li>{SIDEBAR_TITLES[i]}</li>' for i in chosen)
    return _with_paragraph('rotating-sidebar', f'<aside>\n<ul>\n{items}\n</ul>\n</aside>')


def _head_refused(request: Request) -> Response:
    """GET answers 200; HEAD answers 403, or 405 on head-405."""
    if request.method == 'HEAD':
        return _plain(html('<p>Refused.</p>', 405 if request.path.endswith('-405') else 403))
    return html(article_page('head-refused'))


def _head_differs(request: Request) -> Response:
    """The ETag of a HEAD is not the ETag of a GET."""
    return _plain(html(article_page('head-differs')), etag='"head"' if request.method == 'HEAD' else '"get"')


def _cdn_headers(request: Request) -> Response:
    """Date is the time of the request, Age is 600 and Last-Modified is constant."""
    return html(article_page('cdn-headers'), headers={
        'date': http_date(request.now), 'age': '600', 'last-modified': http_date(EPOCH)})


def _new_link(request: Request) -> Optional[Response]:
    """The hub links to the pages of the last seven dates; a dated page is 404 for a later date."""
    name = request.path.removeprefix('/chameleons/new-link/')
    if name == 'hub':
        return html(article_page('new-link-hub', [f'/chameleons/new-link/{d}' for d in daily_dates(request)]))
    day = parse_date(name)
    return html(article_page(f'new-link-{day}')) if day and day <= today(request) else None


def _present(request: Request) -> bool:
    """True in the first 7 days of each 14."""
    return day_number(request) % 14 < 7


def _removed(request: Request) -> Response:
    """200 when present, else 404 (410 on removed-410)."""
    name = request.path.removeprefix('/chameleons/')
    if _present(request):
        return html(article_page(name))
    return not_found() if name == 'removed-404' else _plain(html('<p>Gone.</p>', 410))


def _moved(request: Request) -> Response:
    """moved-old is 200 when present, else 301 to moved-new; moved-new is always 200 with a canonical on itself."""
    if request.path == '/chameleons/moved-new':
        canonical = f'<link rel="canonical" href="{escape(request.url(request.path), quote=True)}">'
        return html(article_page('moved-new', head_html=canonical))
    return html(article_page('moved-old')) if _present(request) else redirect('/chameleons/moved-new')


def _outage(request: Request) -> Response:
    """503 when N is odd."""
    return _plain(html('<p>Unavailable.</p>', 503)) if day_number(request) % 2 else html(article_page('outage'))


def _outage_section(request: Request) -> Optional[Response]:
    """The source page answers 503 when N is odd and links to three articles that are always 200."""
    name = request.path.removeprefix('/chameleons/outage-section/')
    if name:
        return html(article_page(f'outage-section-{name}')) if name in ('1', '2', '3') else None
    if day_number(request) % 2:
        return _plain(html('<p>Unavailable.</p>', 503))
    return html(article_page('outage-section', [f'/chameleons/outage-section/{i}' for i in (1, 2, 3)]))


def _case(name: str, behavior: str, handler: Callable[[Request], Optional[Response]], *tags: str,
          paths: tuple[str, ...] = ()) -> Case:
    """A chameleons case; the path defaults to /chameleons/<name>."""
    return Case('chameleons', name, paths or (f'/chameleons/{name}',), behavior, handler, tags)


CASES: list[Case] = [
    _case('honest-edit', 'The text changes with N; ETag and Last-Modified change with it', _honest_edit, 'first'),
    _case('silent-edit', 'The text changes with N; ETag and Last-Modified never change; a conditional GET answers 304',
          _silent_edit, 'first'),
    _case('restless-header', 'The text never changes; Last-Modified is the time of the request; no ETag',
          _restless_header, 'first'),
    _case('restless-markup', 'The text never changes; a comment and a data attribute have a new token on each request',
          _restless_markup),
    _case('visible-timestamp', 'A paragraph has "Generated at" and the time of the request',
          lambda request: _with_paragraph('visible-timestamp', f'<p>Generated at {request.now.isoformat()}</p>')),
    _case('rotating-sidebar', 'The article is constant; an aside lists 3 of 10 titles, selected by the request time',
          _sidebar),
    _case('counter', 'A paragraph has "Viewed n times"; n is the Unix time of the request',
          lambda request: _with_paragraph('counter', f'<p>Viewed {int(request.now.timestamp())} times</p>')),
    _case('no-validators', 'No ETag, no Last-Modified',
          lambda request: _plain(html(article_page('no-validators'))), 'first'),
    _case('head-refused', 'GET 200 with an ETag; HEAD 403; head-405 answers 405 to HEAD', _head_refused, 'first',
          paths=('/chameleons/head-refused', '/chameleons/head-405')),
    _case('head-differs', 'The ETag of a HEAD is not the ETag of a GET', _head_differs),
    _case('cdn-headers', 'Date is the time of the request, Age is 600, Last-Modified is constant', _cdn_headers),
    _case('new-link', 'The hub links to the dated pages of the last seven dates; a later date answers 404', _new_link,
          paths=('/chameleons/new-link/hub', '/chameleons/new-link/<date>')),
    _case('removed-page', '200 when N mod 14 is below 7, else 404 (410 for removed-410)', _removed,
          paths=('/chameleons/removed-404', '/chameleons/removed-410')),
    _case('moved-page', '200 when N mod 14 is below 7, else 301 to moved-new, a page with a canonical on itself',
          _moved, paths=('/chameleons/moved-old', '/chameleons/moved-new')),
    _case('outage', '503 when N is odd, 200 when even', _outage),
    _case('outage-section', 'The source URL page answers 503 when N is odd; it links to three articles',
          _outage_section, 'own source', paths=('/chameleons/outage-section/', '/chameleons/outage-section/<n>')),
    section_case('chameleons', 'Chameleons: sourdough pages that change between fetches', [
        '/chameleons/honest-edit', '/chameleons/silent-edit', '/chameleons/restless-header',
        '/chameleons/restless-markup', '/chameleons/visible-timestamp', '/chameleons/rotating-sidebar',
        '/chameleons/counter', '/chameleons/no-validators', '/chameleons/head-refused', '/chameleons/head-differs',
        '/chameleons/cdn-headers', '/chameleons/new-link/hub', '/chameleons/removed-404', '/chameleons/removed-410',
        '/chameleons/moved-old', '/chameleons/outage']),
]
