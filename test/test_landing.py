import json
import re
from datetime import datetime, timezone
from html import unescape

import pytest

from afm_pathological.hosts import HOSTS
from afm_pathological.model import Request
from afm_pathological.readme import PREVIEW_DESCRIPTION, PREVIEW_TITLE, RELATED_PROJECTS, landing_markdown
from afm_pathological.site import respond
from test_readme import FORBIDDEN, _visible_words

DOMAIN = 'pathological.answersfrom.me'
SITE_DOMAINS = [DOMAIN, f'www.{DOMAIN}', 'PATHOLOGICAL.AnswersFrom.Me', 'localhost:8080', '127.0.0.1:8080',
                'my-service.example.app', 'nobody.localhost']


@pytest.mark.parametrize('host', SITE_DOMAINS)
def test_site_domain_root_is_the_landing_page(fetch, host):
    """A Host that names no host answers / with the landing page, for GET and HEAD."""
    response = fetch('/', host=host)
    assert response.status == 200 and response.headers['content-type'] == 'text/html; charset=utf-8'
    assert '<h1>Pathological test site' in response.body.decode()
    head = fetch('/', host=host, method='HEAD')
    assert head.status == 200 and head.body == b'' and head.headers['content-length'] == str(len(response.body))


def test_www_is_dropped_from_the_site_domain(fetch):
    """www. of the site domain is not part of the host links."""
    assert fetch('/', host=f'www.{DOMAIN}').body == fetch('/', host=DOMAIN).body


def test_site_domain_paths(fetch):
    """/README.md is the Markdown, /clock and robots.txt answer, every other path is 404 with the host names."""
    markdown = fetch('/README.md', host=DOMAIN)
    assert markdown.headers['content-type'] == 'text/markdown; charset=utf-8'
    assert markdown.body.decode() == landing_markdown('https', DOMAIN)
    assert json.loads(fetch('/clock', host=DOMAIN).body)['date'] == '2026-11-25'
    robots = fetch('/robots.txt', host=DOMAIN)
    assert robots.headers['content-type'].startswith('text/plain')
    assert robots.body.decode() == 'User-agent: *\nAllow: /$\nDisallow: /\n'
    for path in ('/articles/starter', '/sitemap.xml', '/feed', '/nothing'):
        response = fetch(path, host=DOMAIN)
        assert response.status == 404 and response.headers['content-type'].startswith('text/plain'), path
        assert all(name in response.body.decode() for name in HOSTS), path


def test_pathological_host_header_wins(fetch):
    """X-Pathological-Host with a host name selects that host; another value is 404 with the host names everywhere."""
    host_readme = fetch('/', host='localhost:8080', headers={'x-pathological-host': 'mirage'}).body.decode()
    assert '<h1>mirage: pathological test site</h1>' in host_readme
    for host in ('localhost:8080', 'librarian.pathological.answersfrom.me'):
        for path in ('/', '/README.md', '/clock', '/robots.txt', '/articles/starter'):
            response = fetch(path, host=host, headers={'x-pathological-host': 'nobody'})
            assert response.status == 404 and response.headers['content-type'].startswith('text/plain'), path
            assert all(name in response.body.decode() for name in HOSTS), path
    assert fetch('/', host='localhost:8080', headers={'x-pathological-host': ''}).status == 200


SOURCE = 'https://github.com/andy-tmpt-me/afm-pathological'
# The links after the host table: the related projects, then the source
TAIL_LINKS = [url for _, url, _ in RELATED_PROJECTS] + [SOURCE]
INTRO_LINKS = ['https://pathological.answersfrom.me', 'https://github.com/andy-tmpt-me/afm-pathological']


def _links(scheme: str, host: str) -> list[str]:
    """The hrefs of the landing page of a scheme and a Host, after the two links of the introduction."""
    html = respond(Request(host=host, path='/', scheme=scheme)).body.decode()
    links = re.findall(r'<a href="([^"]+)">', html)
    assert links[:2] == INTRO_LINKS
    return links[2:]


@pytest.mark.parametrize('scheme, host', [('https', DOMAIN), ('http', 'localhost:8080')])
def test_host_links_use_scheme_and_site_domain(scheme, host):
    """Each host is linked once, in table order, with the scheme and the site domain; www.janus has a link too."""
    links = _links(scheme, host)
    assert links[:len(HOSTS)] == [f'{scheme}://{name}.{host}/' for name in HOSTS]
    assert links[len(HOSTS):] == [f'{scheme}://www.janus.{host}/', *TAIL_LINKS]


def test_table_has_each_host_once():
    """The table has one row per host with its character and root text."""
    markdown = landing_markdown('https', DOMAIN).split('## How a host is selected')[0]
    rows = [line for line in markdown.splitlines() if line.startswith('| [')]
    assert [re.match(r'\| \[([^\]]+)\]', row).group(1) for row in rows] == list(HOSTS)
    for row, host in zip(rows, HOSTS.values()):
        assert f'| {host.character} |' in row
    assert '`robots.txt` has no `Sitemap` line' in rows[-1]


def test_landing_page_rules(fetch):
    """No forbidden markers, no sitemap directive, a long title, one h1, 200 words or more, the same body any time."""
    response = fetch('/', host=DOMAIN)
    html = response.body.decode()
    for marker in FORBIDDEN:
        assert marker not in html
    assert 'sitemap:' not in html.lower() and html.count('<h1>') == 1
    assert len(unescape(re.search(r'<title>(.*?)</title>', html).group(1))) > 10
    assert _visible_words(html) >= 200
    assert fetch('/', host=DOMAIN, now=datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)).body == response.body
    assert 'X-Pathological-Host' in html and 'X-Pathological-Date' in html and '/clock' in html
    assert '30-second slots' in html


def test_landing_page_goes_through_finish(fetch):
    """The landing page has validators and answers 304 to a matching conditional GET."""
    response = fetch('/', host=DOMAIN)
    assert 'last-modified' in response.headers
    again = fetch('/', host=DOMAIN, headers={'if-none-match': response.headers['etag']})
    assert again.status == 304 and again.body == b''


def test_only_the_landing_page_can_be_indexed(fetch):
    """The landing page has no noindex, also as HEAD and as 304; each other answer of the site has noindex."""
    response = fetch('/', host=DOMAIN)
    not_modified = fetch('/', host=DOMAIN, headers={'if-none-match': response.headers['etag']})
    for landing in (response, not_modified, fetch('/', host=DOMAIN, method='HEAD'), fetch('/', host='localhost:8080')):
        assert landing.headers['x-robots-tag'] == 'nofollow'
    for path in ('/README.md', '/robots.txt', '/clock', '/nothing'):
        assert fetch(path, host=DOMAIN).headers['x-robots-tag'] == 'noindex, nofollow', path
    for name in HOSTS:
        assert fetch('/', host=f'{name}.{DOMAIN}').headers.get('x-robots-tag') in ('noindex, nofollow', None), name
    assert fetch('/', host=DOMAIN, headers={'x-pathological-host': 'breadcrumbs'}).headers['x-robots-tag'] == \
        'noindex, nofollow'


@pytest.mark.parametrize('host, base', [('127.0.0.1:8080', 'localhost:8080'), ('[::1]:8080', 'localhost:8080'),
                                        ('127.0.0.2', 'localhost')])
def test_loopback_site_domain_links_to_localhost(host, base):
    """A loopback IP site domain links each host under localhost with the port."""
    links = _links('http', host)
    assert links[:len(HOSTS)] == [f'http://{name}.{base}/' for name in HOSTS]
    assert links[len(HOSTS)] == f'http://www.janus.{base}/'


@pytest.mark.parametrize('host', ['10.0.0.5:8080', '[2001:db8::1]:8080'])
def test_other_ip_site_domain_has_no_host_links(host):
    """Another IP site domain names the hosts with no link and says to send X-Pathological-Host."""
    html = respond(Request(host=host, path='/', scheme='http')).body.decode()
    assert _links('http', host) == TAIL_LINKS
    assert 'not links: send the request header <code>X-Pathological-Host: &lt;host name&gt;</code>' in html
    assert all(f'<td><code>{name}</code></td>' in html for name in HOSTS)


def test_landing_page_starts_with_the_authors_introduction(fetch):
    """The introduction comes first, with links to the demo site and to the source."""
    html = fetch('/', host=DOMAIN).body.decode()
    assert html.index('predictably an asshole all the time') < html.index('What it is') < html.index('Hosts</h2>')
    assert '<a href="https://pathological.answersfrom.me">' in html
    assert '<a href="https://github.com/andy-tmpt-me/afm-pathological">' in html
    assert 'I hope it fails miserably for you!' in html


def test_related_projects_table(fetch):
    """The Related Projects section is between the time section and the source, with one linked row per project."""
    html = fetch('/', host=DOMAIN).body.decode()
    assert html.index('How time works</h2>') < html.index('Related Projects</h2>') < html.index('Source</h2>')
    assert '<th>Project</th>' in html and '<th>What it is</th>' in html
    assert len({name for name, _, _ in RELATED_PROJECTS}) == len(RELATED_PROJECTS) >= 10
    for name, url, what in RELATED_PROJECTS:
        assert f'<td><a href="{url}">{name}</a></td>' in html
        assert url.startswith('https://') and what.endswith('.') and '|' not in what


def test_link_preview_tags(fetch):
    """The landing page has the preview title and the upside-down description in its head; a host README has none."""
    html = fetch('/', host=DOMAIN).body.decode()
    head = html[:html.index('</head>')]
    assert f'<meta property="og:title" content="{PREVIEW_TITLE}">' in head
    assert f'<title>{PREVIEW_TITLE}</title>' in head
    assert '<h1>Pathological test site: hosts that misbehave on purpose</h1>' in html
    assert PREVIEW_TITLE.startswith('Pathological Webserver: ') and PREVIEW_TITLE.endswith(PREVIEW_DESCRIPTION[1:])
    assert f'<meta property="og:description" content="{PREVIEW_DESCRIPTION}">' in head
    assert PREVIEW_DESCRIPTION[::-1].startswith('∀ ') and PREVIEW_DESCRIPTION.startswith('˙')
    for other in (fetch('/'), fetch('/README.md', host=DOMAIN)):
        assert 'property="og:' not in other.body.decode()
