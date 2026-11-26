from typing import Optional

from afm_pathological.catalog import Case, section_case
from afm_pathological.clock import in_error_slot
from afm_pathological.families.potholes import CHALLENGE
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_page
from afm_pathological.responses import html


def _refused(response: Response) -> Response:
    """The response with no validators of the site."""
    response.validators = False
    return response


def _stale_browser(request: Request) -> Response:
    """403 when the User-Agent has Chrome/120.0.0.0, an article for each other request."""
    if 'Chrome/120.0.0.0' in request.headers.get('user-agent', ''):
        return _refused(html('<p>Your browser is out of date.</p>', 403))
    return html(article_page('stale-browser'))


def _needs_headers(request: Request) -> Response:
    """403 when Accept-Language or Sec-Fetch-Mode is missing."""
    if 'accept-language' not in request.headers or 'sec-fetch-mode' not in request.headers:
        return _refused(html('<p>This request does not look like a browser.</p>', 403))
    return html(article_page('needs-headers'))


def _rate(request: Request) -> Optional[Response]:
    """The source page with 30 links, and each of its 30 pages: 429 in the error slot, an article in the ok slot."""
    number = request.path.removeprefix('/bouncer/rate/')
    if not number:
        return html(article_page('bouncer-rate', [f'/bouncer/rate/{n}' for n in range(1, 31)]))
    if number not in {str(n) for n in range(1, 31)}:
        return None
    if in_error_slot(request):
        response = _refused(html('<p>Too many requests.</p>', 429))
        response.headers['retry-after'] = '30'
        return response
    return html(article_page(f'bouncer-rate-{number}'))


CASES: list[Case] = [
    section_case('bouncer', 'Bouncer: refusals of automated requests',
                 ['/bouncer/stale-browser', '/bouncer/needs-headers', '/bouncer/challenge']),
    Case('bouncer', 'stale-browser', ('/bouncer/stale-browser',),
         '403 when the User-Agent has Chrome/120.0.0.0; 200 for each other request', _stale_browser,
         ('production only',)),
    Case('bouncer', 'needs-headers', ('/bouncer/needs-headers',),
         '403 when the request has no Accept-Language or no Sec-Fetch-Mode header', _needs_headers),
    Case('bouncer', 'rate-limit', ('/bouncer/rate/', '/bouncer/rate/<n>'),
         'The source URL page links to 30 pages; each answers 429 with Retry-After: 30 in seconds 0 to 29 of each '
         'minute', _rate, ('own source', 'local only')),
    Case('bouncer', 'challenge-page', ('/bouncer/challenge',),
         '200 text/html with the title "Just a moment..." and the string cf-chl', lambda request: html(CHALLENGE)),
]
