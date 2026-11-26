import json
from dataclasses import dataclass
from html import escape
from typing import Callable, Optional

from afm_pathological.clock import EPOCH, http_date
from afm_pathological.content import article
from afm_pathological.families.feeds import RSS_TYPE, at_six, daily_rss, recent_dates
from afm_pathological.host_rules import (ROBOTS_CASES, chicken_little_after, chicken_little_root, doorman_before,
                                         forwarding_address_before, hoarder_root, janus_root, rip_van_winkle_after,
                                         rip_van_winkle_before, rip_van_winkle_root, robots, root_page_as,
                                         sloth_after, squirrel_root, tipsy_cartographer_root, yes_man_before)
from afm_pathological.model import Request, Response
from afm_pathological.responses import text, xml
from afm_pathological.sitemaps import regular_urls, urlset

HOST_ROOT_PATHS = frozenset(('/robots.txt', '/sitemap.xml', '/feed', '/rss.xml', '/atom.xml', '/feed.xml',
                             '/index.xml', '/rss2.xml'))


@dataclass(frozen=True)
class RootUrl:
    """One host-root URL of a host as the README lists it."""
    path: str
    status: int
    content_type: str  # the media type without parameters
    behavior: str


@dataclass(frozen=True)
class HostSpec:
    """One host of the spec: its table cells and the functions that give its behavior."""
    name: str  # 'breadcrumbs'
    character: str  # the "Character" cell of the spec
    root_says: str  # the "What the host root says" cell of the spec
    build: str  # 'First', 'Next' or 'Later'
    root: Optional[Callable[[Request], Optional[Response]]] = None  # host-root URLs and other host-only paths
    before: Optional[Callable[[Request], Optional[Response]]] = None  # can answer any request first
    after: Optional[Callable[[Request, Response], Response]] = None  # can change any response last
    start_links: tuple[str, ...] = ('/articles/', '/notes/', '/daily/')
    head_html: str = ''  # extra elements for the <head> of the root page
    root_urls: tuple[RootUrl, ...] = ()  # each host-root URL that does not give the default 404, for the README
    other_root_answer: str = '404'  # what a host-root URL that root_urls does not list answers, for the README
    table_says: str = ('Each host serves the same page families at the same paths. The table lists every other URL '
                       'that this host serves.')  # the first sentences of the README table of all other URLs


def is_host_root(path: str) -> bool:
    """True for a URL that a crawler reads from a host root, other than /."""
    return path in HOST_ROOT_PATHS or path.startswith('/wp-json/')


def regular_sitemap(request: Request) -> Response:
    """The sitemap of the 18 regular URLs with true lastmod dates and Last-Modified."""
    urls = regular_urls(request)
    response = xml(urlset([(loc, day.isoformat()) for loc, day in urls]))
    response.headers['last-modified'] = http_date(max(day for _, day in urls))
    return response


_ROBOTS = RootUrl('/robots.txt', 200, 'text/plain', '`User-agent: *` and `Disallow: /`, nothing else')
_ROBOTS_LISTING = RootUrl('/robots.txt', 200, 'text/plain',
                          '`User-agent: *`, `Disallow: /` and a line that names the absolute URL of `/sitemap.xml`')


def _breadcrumbs(request: Request) -> Optional[Response]:
    """robots.txt with no Sitemap line."""
    return robots(request) if request.path == '/robots.txt' else None


def _mirage(request: Request) -> Optional[Response]:
    """robots.txt that lists /sitemap.xml, which is not there."""
    return robots(request, '/sitemap.xml') if request.path == '/robots.txt' else None


def _librarian(request: Request) -> Optional[Response]:
    """mirage's robots.txt, and the sitemap that it lists."""
    return regular_sitemap(request) if request.path == '/sitemap.xml' else _mirage(request)


_FEED = RootUrl('/feed', 200, RSS_TYPE, 'The daily feed as RSS 2.0: the last 10 daily pages, newest first')


def _routes(routes: dict[str, Callable[[Request], Response]]) -> Callable[[Request], Optional[Response]]:
    """A root function that answers each path of the routes with its function and any other path with None."""
    return lambda request: routes[request.path](request) if request.path in routes else None


def _wp_posts(request: Request) -> Response:
    """The 10 daily pages as WordPress REST post objects."""
    posts = [{'id': 1000 + (day - EPOCH).days, 'date': at_six(day).strftime('%Y-%m-%dT%H:%M:%S'),
              'link': request.url(f'/daily/{day}'), 'title': {'rendered': article(f'daily-{day}').title},
              'excerpt': {'rendered': f'<p>{escape(article(f"daily-{day}").paragraphs[0])}</p>'}}
             for day in recent_dates(request, 10)]
    return text(json.dumps(posts), content_type='application/json')


def _no_head(request: Request) -> Optional[Response]:
    """405 for each HEAD request, with the allow header."""
    if request.method != 'HEAD':
        return None
    response = text('Method not allowed.\n', status=405)
    response.headers['allow'] = 'GET'
    return response


_MAP = 'application/xml'
_ROBOTS_CASE_LIST = '; '.join(
    [f'`/robots.txt?case={case}` lists {" and ".join(f"`{path}`" for path in paths)}'
     for case, paths in ROBOTS_CASES.items()] +
    ['`/robots.txt?case=forms` lists `/maps/good.xml` as an absolute URL, `/maps/old.xml` in a comment and '
     '`/maps/relative.xml` as a relative URL'])
_TIPSY_ROOT_URLS = (
    RootUrl('/robots.txt', 200, 'text/plain',
            '`User-agent: *`, `Disallow: /` and five sitemap lines; `?case=` gives these variants: '
            + _ROBOTS_CASE_LIST),
    RootUrl('/maps/good.xml', 200, _MAP, 'The 18 URLs, with a PHP warning before `<?xml`'),
    RootUrl('/maps/missing.xml', 404, 'text/html', 'Not found'),
    RootUrl('/maps/feed.xml', 200, RSS_TYPE, _FEED.behavior),
    RootUrl('/maps/elsewhere.xml', 200, _MAP, 'Two URLs, one of `librarian` and one of `example.com`'),
    RootUrl('/maps/malformed.xml', 200, _MAP, 'A `<urlset>` that ends in the middle of a `<loc>`'),
    RootUrl('/maps/index-broken.xml', 200, _MAP, 'A sitemap index of `/maps/good.xml` and `/maps/missing.xml`'),
    RootUrl('/maps/text-after.xml', 200, _MAP, 'The 18 URLs, then text after the end of the `<urlset>`'),
    RootUrl('/maps/no-namespace.xml', 200, _MAP, 'The 18 URLs in a `<urlset>` with no `xmlns`'),
    RootUrl('/maps/latin1.xml', 200, _MAP, 'The 18 URLs as Latin-1 bytes with a header of `charset=utf-8`'),
    RootUrl('/maps/good.xml.gz', 200, 'application/gzip', 'The gzip bytes of `/maps/good.xml`, with no '
            '`Content-Encoding`'),
    RootUrl('/maps/self-index.xml', 200, _MAP, 'A sitemap index that lists itself'),
    RootUrl('/maps/relative.xml', 200, _MAP, 'One URL'),
    RootUrl('/maps/old.xml', 200, _MAP, 'One URL'),
)

HOSTS: dict[str, HostSpec] = {spec.name: spec for spec in (
    HostSpec('breadcrumbs', 'You find its pages only by following links',
             '`robots.txt` with no `Sitemap:` line. No feed, no `/sitemap.xml`, no `/wp-json`', 'First',
             root=_breadcrumbs, root_urls=(_ROBOTS,)),
    HostSpec('librarian', 'Keeps an accurate catalog',
             '`robots.txt` lists `/sitemap.xml`. Each `lastmod` is the true date of the last change. ETag and '
             'Last-Modified are true; a conditional GET answers 304', 'First', root=_librarian,
             root_urls=(_ROBOTS_LISTING, RootUrl('/sitemap.xml', 200, 'application/xml',
                                                 'The 18 regular URLs, each with the true date of its last change'))),
    HostSpec('town-crier', 'Announces everything in a feed',
             'An RSS feed at `/feed`. `robots.txt` with no `Sitemap:` line', 'First',
             root=_routes({'/robots.txt': robots, '/feed': daily_rss}), root_urls=(_ROBOTS, _FEED)),
    HostSpec('mirage', 'Promises a map that is not there',
             '`robots.txt` lists `/sitemap.xml`, which answers 404', 'First', root=_mirage,
             root_urls=(_ROBOTS_LISTING, RootUrl('/sitemap.xml', 404, 'text/html', 'Not found'))),
    HostSpec('chicken-little', 'Says that everything changed, each time',
             'As `librarian`, but each `lastmod`, and the ETag and Last-Modified of each response, are the time of '
             'the request. The text of the 18 pages of its sitemap never changes', 'Next',
             root=chicken_little_root, after=chicken_little_after,
             root_urls=(_ROBOTS_LISTING, RootUrl('/sitemap.xml', 200, 'application/xml',
                                                 'The 18 regular URLs, each with the time of the request as lastmod'))),
    HostSpec('rip-van-winkle', 'Says that nothing changes',
             'As `librarian`, but each `lastmod` is `2026-01-01`, also for new pages. The ETag and Last-Modified of '
             'each response never change and each conditional GET answers 304. Its sitemap lists 20 URLs: the 18, '
             'and `/chameleons/honest-edit` and `/chameleons/silent-edit`, whose text changes each day', 'Next',
             root=rip_van_winkle_root, before=rip_van_winkle_before, after=rip_van_winkle_after,
             root_urls=(_ROBOTS_LISTING, RootUrl('/sitemap.xml', 200, 'application/xml',
                                                 'The 20 URLs, each with `2026-01-01` as lastmod'))),
    HostSpec('hoarder', 'Has more pages than a crawler probably wants',
             '`robots.txt` lists `/sitemap_index.xml`: five nested sitemaps of 100 constant articles each '
             '(`/hoard/1` to `/hoard/500`). The fifth also lists the seven daily pages, at its end: 507 URLs. The '
             'index has no dates', 'Next', root=hoarder_root,
             root_urls=(RootUrl('/robots.txt', 200, 'text/plain',
                                '`User-agent: *`, `Disallow: /` and a line that names the absolute URL of '
                                '`/sitemap_index.xml`'),
                        RootUrl('/sitemap_index.xml', 200, 'application/xml',
                                'A sitemap index of `/sitemaps/1.xml` to `/sitemaps/5.xml`, with no dates'),
                        RootUrl('/sitemaps/1.xml', 200, 'application/xml', 'The URLs `/hoard/1` to `/hoard/100`'),
                        RootUrl('/sitemaps/2.xml', 200, 'application/xml', 'The URLs `/hoard/101` to `/hoard/200`'),
                        RootUrl('/sitemaps/3.xml', 200, 'application/xml', 'The URLs `/hoard/201` to `/hoard/300`'),
                        RootUrl('/sitemaps/4.xml', 200, 'application/xml', 'The URLs `/hoard/301` to `/hoard/400`'),
                        RootUrl('/sitemaps/5.xml', 200, 'application/xml',
                                'The URLs `/hoard/401` to `/hoard/500`, then the seven daily pages'))),
    HostSpec('squirrel', 'Has a map and tells no one',
             '`/sitemap.xml` exists with no `lastmod`. `/robots.txt` answers 404', 'Next',
             root=squirrel_root,
             root_urls=(RootUrl('/sitemap.xml', 200, 'application/xml', 'The 18 regular URLs, with no lastmod'),)),
    HostSpec('headless-horseman', 'Cannot answer a HEAD request',
             'Each HEAD answers 405. GET is normal. An RSS feed at `/feed`. `robots.txt` with no `Sitemap:` line',
             'Next', root=_routes({'/robots.txt': robots, '/feed': daily_rss}), before=_no_head,
             root_urls=(_ROBOTS, _FEED)),
    HostSpec('tipsy-cartographer', 'Draws maps that are wrong',
             '`robots.txt` lists five sitemaps: `/maps/good.xml` (the 18 URLs, with a PHP warning before `<?xml`), '
             '`/maps/missing.xml` (404), `/maps/feed.xml` (an RSS feed), `/maps/elsewhere.xml` (only URLs of '
             '`librarian` and `example.com`) and `/maps/malformed.xml` (XML that does not parse)', 'Later',
             root=tipsy_cartographer_root, root_urls=_TIPSY_ROOT_URLS),
    HostSpec('gutenberg', 'Is a WordPress site',
             '`/wp-json/wp/v2/posts` answers with JSON. The root page has '
             '`<meta name="generator" content="WordPress 6.6">`. An RSS feed at `/feed`', 'Later',
             root=_routes({'/feed': daily_rss, '/wp-json/wp/v2/posts': _wp_posts}),
             head_html='<meta name="generator" content="WordPress 6.6">',
             root_urls=(_FEED, RootUrl('/wp-json/wp/v2/posts', 200, 'application/json',
                                       'The 10 daily pages as WordPress post objects'))),
    HostSpec('yes-man', 'Answers 200 to everything',
             'Each path returns the README as `text/html`, also `/robots.txt`, `/feed`, `/index.xml`, `/sitemap.xml` '
             'and `/wp-json/wp/v2/posts`, for GET and HEAD', 'Later',
             before=yes_man_before,
             root_urls=tuple(RootUrl(path, 200, 'text/html', 'The HTML of the root page') for path in (
                 '/robots.txt', '/feed', '/index.xml', '/sitemap.xml', '/wp-json/wp/v2/posts')),
             other_root_answer='200 with the HTML of the root page, as each other path does',
             table_says='On this host each URL of the table, as each other path except `/clock` and `/README.md`, '
                        'answers 200 with the HTML of the root page. The table lists what the other hosts serve.'),
    HostSpec('sloth', 'Takes its time',
             '`robots.txt`, with no `Sitemap:` line, answers after 15 s. Each HEAD answers after 12 s. Each other '
             'response answers after 2 s. A longer delay of a case stays: `/potholes/slow-get` answers a GET after '
             '35 s', 'Later', root=_routes({'/robots.txt': robots}), after=sloth_after,
             root_urls=(RootUrl('/robots.txt', 200, 'text/plain',
                                '`User-agent: *`, `Disallow: /` and nothing else, after 15 s'),)),
    HostSpec('whisperer', 'Names its feed only in the head of its root page',
             'No feed at the six root paths, no sitemap, `robots.txt` with no `Sitemap:` line. The README has '
             '`<link rel="alternate" type="application/rss+xml" href="/dispatches">`. `/dispatches` is an RSS feed',
             'Later', root=_routes({'/robots.txt': robots, '/dispatches': daily_rss}),
             head_html='<link rel="alternate" type="application/rss+xml" href="/dispatches">',
             root_urls=(_ROBOTS, RootUrl('/dispatches', 200, RSS_TYPE, _FEED.behavior))),
    HostSpec('masquerade', 'Serves its root page as XML',
             '`/index.xml` returns the README HTML as `application/xml`. `/feed` returns it as `text/html`', 'Later',
             root=_routes({'/index.xml': root_page_as('application/xml'), '/feed': root_page_as('text/html')}),
             root_urls=(RootUrl('/index.xml', 200, 'application/xml', 'The HTML of the root page'),
                        RootUrl('/feed', 200, 'text/html', 'The HTML of the root page'))),
    HostSpec('janus', 'One site with two names',
             'Two hostnames, same content. `robots.txt` lists `/sitemap.xml`. Each of its 18 URLs has the apex name. '
             'After the apex entry of `/articles/starter` it lists that page two more times: with the `www.` name, '
             'and with the host in upper case',
             'Later', root=janus_root,
             root_urls=(_ROBOTS_LISTING, RootUrl('/sitemap.xml', 200, 'application/xml',
                                                 'The 18 URLs with the apex name, and two more entries of '
                                                 '`/articles/starter`: with the `www.` name and in upper case'))),
    HostSpec('forwarding-address', 'Moved away',
             'Each path except `/README.md` and `/clock`, also `/robots.txt`, answers 301 to the same path on '
             '`librarian`', 'Later',
             before=forwarding_address_before,
             root_urls=tuple(RootUrl(path, 301, 'text/plain', 'Redirects to the same path on `librarian`')
                             for path in ('/robots.txt', '/sitemap.xml')),
             other_root_answer='301 to the same path on `librarian`, as each other path does except `/README.md` '
                               'and `/clock`',
             table_says='On this host each URL of the table answers 301 to the same path on `librarian`. The table '
                        'lists what `librarian` serves.'),
    HostSpec('doorman', 'Lets in only guests that it does not know',
             'Each request with a Chrome 120 User-Agent (`Chrome/120.0.0.0`) answers 403, also '
             '`/robots.txt` and each HEAD. Each other request is normal. `robots.txt` has no `Sitemap:` line',
             'Later', root=_routes({'/robots.txt': robots}), before=doorman_before,
             root_urls=(_ROBOTS,)),
)}


def resolve(host_header: str) -> tuple[Optional[HostSpec], bool]:
    """The host spec of a Host header and whether it has the www. prefix: the first label after an optional www."""
    name = host_header.lower().split(':', 1)[0]
    is_www = name.startswith('www.')
    spec = HOSTS.get(name.removeprefix('www.').split('.', 1)[0])
    return spec, is_www and spec is not None
