import gzip
import hashlib
import re
from dataclasses import replace
from datetime import timezone
from typing import Callable, Optional
from urllib.parse import parse_qs

from afm_pathological.clock import EPOCH, http_date
from afm_pathological.families.feeds import daily_rss
from afm_pathological.families.regulars import HOARD_PAGES, daily_dates
from afm_pathological.model import Request, Response
from afm_pathological.responses import html, not_found, redirect, text, xml
from afm_pathological.sitemaps import regular_urls, sitemap_index, urlset

Entries = Callable[[Request], list[tuple[str, Optional[str]]]]
_CHAMELEONS = ('/chameleons/honest-edit', '/chameleons/silent-edit')
_PHP_WARNING = '<br />\n<b>Warning</b>: Undefined variable $x in <b>/var/www/sitemap.php</b>\n'
_GOOD, _MISSING, _FEED, _ELSEWHERE, _MALFORMED = (f'/maps/{name}.xml' for name in (
    'good', 'missing', 'feed', 'elsewhere', 'malformed'))
ROBOTS_CASES = {  # the sitemaps that robots.txt?case=<case> lists, by the name of the case
    'nested': ['/maps/index-broken.xml'], 'after': [_GOOD, '/maps/text-after.xml'],
    'no-namespace': [_GOOD, '/maps/no-namespace.xml'], 'latin1': [_GOOD, '/maps/latin1.xml'],
    'gz': [_GOOD, '/maps/good.xml.gz'], 'self': ['/maps/self-index.xml']}


def robots(request: Request, *sitemaps: str) -> Response:
    """A robots.txt that disallows all, with a Sitemap line for each sitemap path."""
    lines = ['User-agent: *', 'Disallow: /', *(f'Sitemap: {request.url(path)}' for path in sitemaps)]
    return text('\n'.join(lines) + '\n')


def _respond_unconditional(request: Request, **changes: str) -> Response:
    """The response of the site to the request with the changes and with no conditional (if-*) header."""
    from afm_pathological.site import respond  # site imports the hosts, which import this module
    headers = {k: v for k, v in request.headers.items() if not k.startswith('if-')}
    return respond(replace(request, headers=headers, **changes))


def root_page_as(content_type: str) -> Callable[[Request], Response]:
    """A function that answers with the HTML of the root page of the same host, under a content type."""
    def answer(request: Request) -> Response:
        page = _respond_unconditional(request, path='/', method='GET')
        return Response(200, {'content-type': content_type}, page.body)
    return answer


def _sitemap_host(entries: Entries, listed: bool = True) -> Callable[[Request], Optional[Response]]:
    """A root function for /sitemap.xml with the entries; with listed, robots.txt names it."""
    def root(request: Request) -> Optional[Response]:
        if listed and request.path == '/robots.txt':
            return robots(request, '/sitemap.xml')
        return xml(urlset(entries(request))) if request.path == '/sitemap.xml' else None
    return root


def _now_z(request: Request) -> str:
    """The time of the request as ISO 8601 with seconds and Z."""
    return request.now.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


chicken_little_root = _sitemap_host(lambda request: [(loc, _now_z(request)) for loc, _ in regular_urls(request)])
rip_van_winkle_root = _sitemap_host(lambda request: [
    (loc, EPOCH.isoformat()) for loc in [*(loc for loc, _ in regular_urls(request)),
                                         *(request.url(path) for path in _CHAMELEONS)]])
squirrel_root = _sitemap_host(lambda request: [(loc, None) for loc, _ in regular_urls(request)], listed=False)


def chicken_little_after(request: Request, response: Response) -> Response:
    """The ETag and Last-Modified of each 200 are the time of the request; a conditional request gets no 304."""
    if response.status == 304:
        return _respond_unconditional(request)
    if response.status == 200:
        response.headers['etag'] = f'"{hashlib.sha256(request.now.isoformat().encode()).hexdigest()[:20]}"'
        response.headers['last-modified'] = http_date(request.now)
    return response


def rip_van_winkle_before(request: Request) -> Optional[Response]:
    """304 for each conditional request."""
    if 'if-none-match' in request.headers or 'if-modified-since' in request.headers:
        return Response(304, {'etag': '"rip"', 'last-modified': http_date(EPOCH)})
    return None


def rip_van_winkle_after(request: Request, response: Response) -> Response:
    """The ETag and Last-Modified of each 200 never change."""
    if response.status == 200:
        response.headers['etag'], response.headers['last-modified'] = '"rip"', http_date(EPOCH)
    return response


HOARD_PER_SITEMAP = 100
HOARD_SITEMAPS = HOARD_PAGES // HOARD_PER_SITEMAP


def hoarder_root(request: Request) -> Optional[Response]:
    """robots.txt, the sitemap index and its sitemaps of HOARD_PER_SITEMAP /hoard pages each."""
    if request.path == '/robots.txt':
        return robots(request, '/sitemap_index.xml')
    if request.path == '/sitemap_index.xml':
        return xml(sitemap_index([request.url(f'/sitemaps/{n}.xml') for n in range(1, HOARD_SITEMAPS + 1)]))
    match = re.fullmatch(r'/sitemaps/([1-9][0-9]*)\.xml', request.path)
    if not match or int(match.group(1)) > HOARD_SITEMAPS:
        return None
    n = int(match.group(1))
    locs = [request.url(f'/hoard/{i}') for i in range(HOARD_PER_SITEMAP * (n - 1) + 1, HOARD_PER_SITEMAP * n + 1)]
    if n == HOARD_SITEMAPS:
        locs += [request.url(f'/daily/{day}') for day in daily_dates(request)]
    return xml(urlset([(loc, None) for loc in locs]))


def _good(request: Request) -> str:
    """The 18 URLs of the regular pages as a sitemap."""
    return urlset([(loc, day.isoformat()) for loc, day in regular_urls(request)])


def _one_url(request: Request, path: str) -> Response:
    """A sitemap of one URL."""
    return xml(urlset([(request.url(path), None)]))


def _maps(request: Request) -> Optional[Response]:
    """The files under /maps/ of tipsy-cartographer."""
    good = _good(request)
    first_loc = good.index('<loc>', good.index('<loc>') + 1) + 12
    answers: dict[str, Callable[[], Response]] = {
        _GOOD: lambda: xml(_PHP_WARNING + good),
        _MISSING: not_found,
        _FEED: lambda: daily_rss(request),
        _ELSEWHERE: lambda: xml(urlset([(request.sibling_url('librarian', '/articles/starter'), None),
                                        ('https://example.com/', None)])),
        _MALFORMED: lambda: xml(good[:first_loc]),
        '/maps/index-broken.xml': lambda: xml(sitemap_index([request.url(_GOOD), request.url(_MISSING)])),
        '/maps/text-after.xml': lambda: xml(good + 'Generated in 0.02 seconds.\n'),
        '/maps/no-namespace.xml': lambda: xml(re.sub(r' xmlns="[^"]*"', '', good)),
        '/maps/latin1.xml': lambda: Response(200, {'content-type': 'application/xml; charset=utf-8'},
                                             good.replace('\n', '\n<!-- café -->\n', 1).encode('latin-1')),
        '/maps/good.xml.gz': lambda: Response(200, {'content-type': 'application/gzip'},
                                              gzip.compress(good.encode(), mtime=0)),
        '/maps/self-index.xml': lambda: xml(sitemap_index([request.url('/maps/self-index.xml')])),
        '/maps/relative.xml': lambda: _one_url(request, '/articles/starter'),
        '/maps/old.xml': lambda: _one_url(request, '/articles/hydration'),
    }
    return answers[request.path]() if request.path in answers else None


def tipsy_cartographer_root(request: Request) -> Optional[Response]:
    """robots.txt with the five wrong sitemaps (or a case of ROBOTS_CASES) and the files under /maps/."""
    if request.path != '/robots.txt':
        return _maps(request)
    case = parse_qs(request.query).get('case', [''])[0]
    if case == 'forms':
        lines = ['User-agent: *', 'Disallow: /', f'Sitemap: {request.url(_GOOD)}', '# Sitemap: /maps/old.xml',
                 'Sitemap: /maps/relative.xml']
        return text('\n'.join(lines) + '\n')
    if case in ROBOTS_CASES:
        return robots(request, *ROBOTS_CASES[case])
    return robots(request, _GOOD, _MISSING, _FEED, _ELSEWHERE, _MALFORMED)


def janus_root(request: Request) -> Optional[Response]:
    """robots.txt and the sitemap with the apex URLs and two more forms of /articles/starter."""
    if request.path == '/robots.txt':
        return robots(request, '/sitemap.xml')
    if request.path != '/sitemap.xml':
        return None
    apex = request.sibling_host('janus')
    entries = []
    for loc, day in regular_urls(request):
        path = loc.removeprefix(request.url(''))
        entries.append((f'{request.scheme}://{apex}{path}', day.isoformat()))
        if path == '/articles/starter':
            entries += [(f'{request.scheme}://{host}{path}', day.isoformat()) for host in (f'www.{apex}', apex.upper())]
    return xml(urlset(entries))


def yes_man_before(request: Request) -> Optional[Response]:
    """The root page for each path except /, /clock and /README.md."""
    if request.path in ('/', '/clock', '/README.md'):
        return None
    return root_page_as('text/html; charset=utf-8')(request)


def sloth_after(request: Request, response: Response) -> Response:
    """15 s for /robots.txt, 12 s for each HEAD, 2 s for each other response; a longer delay of a case stays."""
    delay = 15 if request.path == '/robots.txt' else 12 if request.method == 'HEAD' else 2
    response.delay_sec = max(response.delay_sec, delay)
    return response


def forwarding_address_before(request: Request) -> Optional[Response]:
    """301 to the same path and query on librarian, for each path except /README.md and /clock."""
    if request.path in ('/README.md', '/clock'):
        return None
    query = f'?{request.query}' if request.query else ''
    response = redirect(request.sibling_url('librarian', f'{request.path}{query}'))
    response.headers['content-type'] = 'text/plain; charset=utf-8'
    response.body = b'Moved permanently.\n'
    return response


def doorman_before(request: Request) -> Optional[Response]:
    """403 for a Chrome 120 User-Agent."""
    if 'Chrome/120.0.0.0' not in request.headers.get('user-agent', ''):
        return None
    response = html('<!DOCTYPE html>\n<html lang="en"><head><title>Forbidden</title></head>'
                    '<body><p>Forbidden.</p></body></html>\n', status=403)
    response.validators = False
    return response
