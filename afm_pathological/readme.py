import ipaddress
import os
import re
from html import escape
from typing import Optional

from afm_pathological.catalog import cases
from afm_pathological.hosts import HOSTS, HostSpec

_DOMAIN = 'pathological.answersfrom.me'
# The name of who runs the site, shown in each host README: unset means the default, empty or blank means no name
OPERATOR_VARIABLE = 'PATHOLOGICAL_OPERATOR'
DEFAULT_OPERATOR = 'Answers From Me'
# The URL of an icon for the browser tab of each README and of the landing page: unset or blank means no icon
FAVICON_VARIABLE = 'PATHOLOGICAL_FAVICON'
_INTRO = (
    'This host is part of the pathological test site{operator}, a web server with predictable bad behavior for '
    'tests of crawlers and scrapers. Each host of the site behaves like one kind of difficult website, and each '
    'page is an article about sourdough baking, so that all pages read as the work of one author. The site keeps no '
    'state: each answer depends only on the request and its time. This page is the README of the host, for manual '
    'debugging, and it is also the first page that a crawl of the host root reads.')
_ROOT_OTHER = ('A host-root URL that is not in a table here (`/robots.txt`, `/sitemap.xml`, the six feed paths and '
               'each path under `/wp-json/`) answers {} on this host.')
_TABLE_INTRO = (
    '{} A URL here is plain text, not a link, so that a crawl of this page reaches only the pages of the list above. '
    'A segment in angle brackets matches any one path segment, and a last segment that ends in `...>` matches the '
    'rest of the path. The tag `own source` marks a case that its section page does not link to, so point a crawler '
    'at the URL itself. The tag `local only` marks a case whose result depends on the second of the request or that '
    'is slow, so assert on it only with a fixed clock. The tag `production only` marks a case whose result depends '
    'on the real network path, such as a proxy or a rendering service between the client and the server, so a test '
    'in the same process cannot show it.')
_TIME_RULES = (
    'Content that changes each day uses the day number N: the number of days from 2026-01-01 to the UTC date of the '
    'request. Content that changes on each request uses the time of the request. The request header '
    '`X-Pathological-Date: YYYY-MM-DD` replaces the UTC date for one request, for manual checks of a different day. '
    'Behavior that needs state on a real site uses time slots: a request in seconds 0 to 29 of the minute is in the '
    'error slot, and a request in seconds 30 to 59 is in the ok slot. A case that fails, then succeeds, answers with '
    'an error in the first slot and with 200 in the second. `/clock` returns the UTC time, the date and N that the '
    'site uses, as JSON.')
_SOURCE = 'https://github.com/andy-tmpt-me/afm-pathological'
_DEMO = f'https://{_DOMAIN}'
# The author's own introduction; the public README has the same text
_LANDING_PITCH = (
    'Web servers are unpredictable assholes, so I finally decided to build one that is predictably an asshole all '
    'the time.',
    'You already know that web servers are assholes if you\'ve ever done any web crawling or scraping: they lie '
    'about timestamps, have missing or outdated sitemaps, return empty responses, and so much more.',
    'So I built a misbehaving web server that predictably exhibits all of the pathologies '
    'I\'ve seen over the years. Honestly I should have done this decades ago. It\'s live at '
    f'[{_DEMO}]({_DEMO}), or you can build and host it yourself ([{_SOURCE}]({_SOURCE})).',
    'If you do anything with web crawling or scraping, feel free to give it a try. I hope it fails miserably for '
    'you!')
_LANDING_INTRO = (
    'This is a web server with predictable bad behavior, for tests of crawlers, scrapers and HTTP clients. Each host '
    'name below selects a behavior of the whole host: how it answers `robots.txt`, sitemaps, feeds, HEAD requests, '
    'conditional requests and user agents. On every host the same page families serve one case per path: redirects, '
    'wrong content types, pages that change each day, link traps, slow and torn responses and more.',
    'Each page is an article about sourdough baking, so that all pages read as the work of one author. The server '
    'keeps no state: each answer depends only on the request and its time. The root page of each host is its README, '
    'which lists every URL of that host with its behavior.')
_SELECTION = (
    'The host is the first label of the `Host` header, after an optional `www.`. The request header '
    '`X-Pathological-Host: <host name>` replaces the `Host` header, so `curl -H \'X-Pathological-Host: breadcrumbs\' '
    '{url}` reaches `breadcrumbs` through this address; a value that is not a host name answers 404 with the list '
    'of host names on every path. With no such header, a `Host` that names no host answers this page at `/` (as '
    'Markdown at `/README.md`), `/clock`, `/preview.jpg` (the image of a link preview), a `robots.txt` that allows '
    'only this page and that image, and 404 on every other path.')
_NO_LINKS = ('This server is reached by an IP address, which has no host names under it, so the hosts below are not '
             'links: send the request header `X-Pathological-Host: <host name>` to reach a host.')
_LANDING_TIME = (
    'Content that changes each day uses the day number: the number of days from 2026-01-01 to the UTC date of the '
    'request. The request header `X-Pathological-Date: YYYY-MM-DD` replaces the date for one request, and `/clock` '
    'returns the UTC time, the date and the day number as JSON. Behavior that needs state uses two 30-second slots: '
    'a request in seconds 0 to 29 of the minute is in the error slot, one in seconds 30 to 59 in the ok slot.')
# Other open-source projects and public sites with a related purpose: name, link, what it is
RELATED_PROJECTS = (
    ('crawler-test.com', 'https://www.crawler-test.com/',
     'A site of test pages for SEO crawlers: titles, description tags, encodings, robots rules, redirects, links, '
     'canonical tags and status codes.'),
    ('Security Crawl Maze', 'https://github.com/google/security-crawl-maze',
     'A test bed for security crawlers. Its pages link to a resource in every way that a web page can, and one '
     'endpoint returns the URLs that a crawler must find.'),
    ('HttpCrawlerTestSite', 'https://github.com/cyotek/HttpCrawlerTestSite',
     'A small PHP site that tests the essential functions of a crawler.'),
    ('Hamms', 'https://github.com/kevinburke/hamms',
     'A badly behaved HTTP server for tests of HTTP clients. Each port has one failure: no answer, a slow answer, '
     'a malformed answer or a closed connection.'),
    ('pathod', 'https://pypi.org/project/pathod/',
     'A pathological HTTP daemon. A small language in the URL builds almost any response, a malformed one '
     'included.'),
    ('huhhttp', 'https://github.com/chfoo/huhhttp',
     'An evil web server that fuzz tests crawlers and download tools with malformed and hostile responses.'),
    ('errorworks (ChaosWeb)', 'https://github.com/johnm-dta/errorworks',
     'Fake servers that inject faults at configured rates. ChaosWeb is the web server for tests of scrapers.'),
    ('go-httpbin', 'https://github.com/mccutchen/go-httpbin',
     'A general HTTP request and response service: status codes, delays, redirects, headers and bodies on '
     'request.'),
    ('Toxiproxy', 'https://github.com/Shopify/toxiproxy',
     'A TCP proxy that adds latency, timeouts and outages between a client and a real server.'),
    ('toscrape.com', 'https://toscrape.com/',
     'Practice sites for web scraping (a book store and a quotes site) that exercise data extraction.'),
    ('Nepenthes', 'https://zadzmo.org/code/nepenthes/',
     'A tarpit that gives unwanted crawlers an endless maze of slow, generated pages.'),
    ('iocaine', 'https://iocaine.madhouse-project.org/',
     'A tarpit that gives unwanted crawlers an endless maze of generated text.'))
_RELATED_INTRO = (
    'These open-source projects and public sites also give a crawler, a scraper or an HTTP client something '
    'difficult to work with.')


def readme_markdown(host: HostSpec) -> str:
    """The README of a host as Markdown, from its spec and the catalog."""
    base = f'https://{host.name}.{_DOMAIN}'
    rows = [f'| {c.family} | {c.name} | `{path}` | {c.behavior} | {", ".join(t for t in c.tags if t != 'first')} |'
            for c in cases() for path in c.paths]
    root_table = ['| URL | Status | Content type | Behavior |', '| --- | --- | --- | --- |',
                  *(f'| `{u.path}` | {u.status} | {u.content_type} | {u.behavior} |' for u in host.root_urls),
                  ''] if host.root_urls else []
    lines = [
        f'# {host.name}: pathological test site', '', f'{host.character}.', '', _INTRO.format(operator=_of_operator()),
        '',
        '## Host root', '', f'{host.root_says}.', '', *root_table, _ROOT_OTHER.format(host.other_root_answer), '',
        '## Start here', '', *(f'- [{link}]({link})' for link in host.start_links), '',
        '## All other URLs', '', _TABLE_INTRO.format(host.table_says), '',
        '| Family | Case | URL | Behavior | Tags |', '| --- | --- | --- | --- | --- |', *rows, '',
        '## Time rules', '', _TIME_RULES, '',
        '```bash', f'curl {base}/clock', f"curl -H 'X-Pathological-Date: 2026-03-01' {base}/daily/", '```', '']
    return _sitemap_safe('\n'.join(lines))


def landing_markdown(scheme: str, domain: str) -> str:
    """The landing page of the site domain as Markdown: what the site is and a linked table of every host."""
    base = _link_domain(domain)

    def name_cell(name: str, label: str) -> str:
        return f'[{label}]({scheme}://{name}.{base}/)' if base else f'`{label}`'

    rows = [f'| {name_cell(h.name, h.name)} | {h.character} | {h.root_says} |' for h in HOSTS.values()]
    janus = name_cell('www.janus', f'www.janus.{base}' if base else 'www.janus')
    no_links = [] if base else [_NO_LINKS, '']
    related = [f'| [{name}]({url}) | {what} |' for name, url, what in RELATED_PROJECTS]
    lines = [
        f'# {PREVIEW_TITLE}', '',
        *(line for paragraph in _LANDING_PITCH for line in (paragraph, '')),
        '## What it is', '', _LANDING_INTRO[0], '', _LANDING_INTRO[1], '',
        '## Hosts', '', *no_links, '| Host | Character | What the host root says |', '| --- | --- | --- |',
        *rows, '', f'The host `janus` also answers at its second name, {janus}.', '',
        '## How a host is selected', '', _SELECTION.format(url=f'{scheme}://{domain}/'), '',
        '## How time works', '', _LANDING_TIME, '',
        '## Related Projects', '', _RELATED_INTRO, '', '| Project | What it is |', '| --- | --- |', *related, '',
        '## Source', '', f'The source code is at [{_SOURCE}]({_SOURCE}), under the MIT licence.', '']
    return _sitemap_safe('\n'.join(lines))


def _of_operator() -> str:
    """' of <name>' with the operator variable, or the default when it is unset; '' when it is blank."""
    name = os.environ.get(OPERATOR_VARIABLE, DEFAULT_OPERATOR).strip()
    return f' of {name}' if name else ''


# What a link preview of the landing page shows. The upside-down look-alike letters say "A web server that
# misbehaves on purpose": the preview misbehaves too. Some platforms show the title only, so the title has them.
# The title is also the heading of the landing page. The description is the first sentence of the introduction
PREVIEW_TITLE = 'Pathological: ǝsodɹnd uo sǝʌɐɥǝqsıɯ ʇɐɥʇ ɹǝʌɹǝs qǝʍ ∀'
PREVIEW_DESCRIPTION = _LANDING_PITCH[0]
PREVIEW_AUTHOR = 'Andy Jenkins'  # who wrote the introduction


# The image of a link preview: the Utah teapot (a classic test object of computer graphics, and HTTP status 418),
# upside down as the title is. A preview needs the full URL of its image
PREVIEW_IMAGE_PATH = '/preview.jpg'
PREVIEW_IMAGE_SIZE = 1200  # pixels, width and height


def preview_html(scheme: str, domain: str) -> str:
    """The Open Graph lines for the head of the landing page of a scheme and a site domain."""
    tags = {'og:type': 'website', 'og:title': PREVIEW_TITLE, 'og:description': PREVIEW_DESCRIPTION,
            'og:author': PREVIEW_AUTHOR,
            'og:image': f'{scheme}://{domain}{PREVIEW_IMAGE_PATH}', 'og:image:type': 'image/jpeg',
            'og:image:width': str(PREVIEW_IMAGE_SIZE), 'og:image:height': str(PREVIEW_IMAGE_SIZE),
            'og:image:alt': 'An upside-down teapot with the upside-down text HTTP/1.1 418 I\'m a teapot'}
    # Some preview readers take the author from the plain author tag and not from og:author
    return f'<meta name="author" content="{escape(PREVIEW_AUTHOR)}">\n' + ''.join(
        f'<meta property="{name}" content="{escape(value)}">\n' for name, value in tags.items())


def favicon_html() -> str:
    """The <link rel="icon"> line for the head of a page, or '' when the favicon variable is unset or blank."""
    url = os.environ.get(FAVICON_VARIABLE, '').strip()
    return f'<link rel="icon" href="{escape(url)}">\n' if url else ''


def _link_domain(domain: str) -> Optional[str]:
    """The domain under which the host names are linked: localhost for a loopback IP, None for another IP literal."""
    if domain.startswith('['):
        address, _, rest = domain[1:].partition(']')
        port = rest.removeprefix(':')
    else:
        address, _, port = domain.partition(':')
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return domain
    return f'localhost{":" + port if port else ""}' if ip.is_loopback else None


def _sitemap_safe(markdown: str) -> str:
    """The Markdown with no robots.txt sitemap directive: a README also answers /robots.txt on some hosts."""
    return re.sub(r'(?i)(sitemap):', r'\1', markdown)


def _inline(value: str) -> str:
    """Code spans and links of one line of Markdown, as HTML."""
    parts = re.split(r'`([^`]*)`', value)
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(f'<code>{escape(part)}</code>')
        else:
            out.append(re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', escape(part)))
    return ''.join(out)


def _cells(row: str) -> list[str]:
    """The cells of one Markdown table row."""
    return [cell.strip() for cell in row.strip().strip('|').split('|')]


def render(markdown: str) -> str:
    """HTML of the Markdown that readme_markdown writes: headings, paragraphs, lists, tables, code."""
    blocks, lines, i = [], markdown.split('\n'), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            end = lines.index('```', i + 1)
            blocks.append(f'<pre><code>{escape(chr(10).join(lines[i + 1:end]))}</code></pre>')
            i = end + 1
            continue
        group = []
        while i < len(lines) and lines[i] and not lines[i].startswith('```'):
            group.append(lines[i])
            i += 1
        if not group:
            i += 1
        elif group[0].startswith('#'):
            level = len(group[0]) - len(group[0].lstrip('#'))
            blocks.append(f'<h{level}>{_inline(group[0][level:].strip())}</h{level}>')
        elif group[0].startswith('- '):
            blocks.append('<ul>\n' + ''.join(f'<li>{_inline(g[2:])}</li>\n' for g in group) + '</ul>')
        elif group[0].startswith('|'):
            head = ''.join(f'<th>{_inline(c)}</th>' for c in _cells(group[0]))
            body = ''.join('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in _cells(g)) + '</tr>\n' for g in group[2:])
            blocks.append(f'<table>\n<tr>{head}</tr>\n{body}</table>')
        else:
            blocks.append(f'<p>{_inline(" ".join(group))}</p>')
    return '\n'.join(blocks)
