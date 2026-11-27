import re
from dataclasses import replace
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser

import pytest

from afm_pathological.catalog import cases
from afm_pathological.hosts import HOSTS
from afm_pathological.readme import readme_markdown, render

FORBIDDEN = ('__NEXT_DATA__', 'window.__NUXT__', 'data-reactroot', '<app-root', 'ng-version', 'id="__next"',
             'id="root"', 'type="password"')


class _Text(HTMLParser):
    """Collects the visible text of the <body> of an HTML document."""

    def __init__(self):
        super().__init__()
        self.in_body = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.in_body = self.in_body or tag == 'body'

    def handle_data(self, data):
        if self.in_body:
            self.parts.append(data)


def _visible_words(html: str) -> int:
    """The number of words of visible text in the body."""
    parser = _Text()
    parser.feed(html)
    return len(' '.join(parser.parts).split())


PAGE_HOSTS = [name for name in HOSTS if name != 'forwarding-address']  # it redirects /, so it has no HTML README


@pytest.mark.parametrize('name', PAGE_HOSTS)
def test_root_page_rules(fetch, name):
    """The root page of each host follows the README rules."""
    response = fetch('/', host=name)
    assert response.status == 200
    assert response.headers['content-type'] == 'text/html; charset=utf-8'
    html = response.body.decode()
    start_links = [f'<a href="{link}">' for link in HOSTS[name].start_links]
    assert re.findall(r'<a [^>]*>', html) == start_links
    for marker in FORBIDDEN:
        assert marker not in html
    assert 'sitemap:' not in html.lower()
    assert _visible_words(html) >= 200
    title = re.search(r'<title>(.*?)</title>', html).group(1)
    assert len(unescape(title)) > 10
    assert html.count('<h1>') == 1
    assert fetch('/', host=name, now=datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)).body == response.body


def test_forwarding_address_readme_is_markdown_only(fetch):
    """/ redirects; the README at /README.md follows the same rules as the other root pages."""
    assert fetch('/', host='forwarding-address').status == 301
    markdown = fetch('/README.md', host='forwarding-address').body.decode()
    assert not any(marker in markdown for marker in FORBIDDEN) and 'sitemap:' not in markdown.lower()
    assert len(markdown.split()) >= 200 and '`/articles/`' in markdown


@pytest.mark.parametrize('name', PAGE_HOSTS)
def test_readme_lists_every_case_path(fetch, name):
    """Each path of each catalog case is in the Markdown and the HTML of the README."""
    markdown = fetch('/README.md', host=name).body.decode()
    html = unescape(fetch('/', host=name).body.decode())
    paths = [path for case in cases() for path in case.paths] + [url.path for url in HOSTS[name].root_urls]
    for path in paths:
        assert f'`{path}`' in markdown, path
        assert f'<code>{path}</code>' in html, path


def test_readme_host_root_table():
    """The host-root table lists each RootUrl with its status, content type and behavior, and the 404 rule."""
    markdown = readme_markdown(HOSTS['mirage'])
    assert '| `/robots.txt` | 200 | text/plain |' in markdown
    assert '| `/sitemap.xml` | 404 | text/html |' in markdown
    assert 'answers 404' in markdown.split('## Start here')[0]
    assert '| URL | Status |' not in readme_markdown(replace(HOSTS['mirage'], root_urls=()))


def test_readme_markdown_contents():
    """The Markdown names the host, its character, its host root, the start links and the time rules."""
    host = HOSTS['librarian']
    markdown = readme_markdown(host)
    assert 'librarian' in markdown.splitlines()[0]
    assert host.character in markdown
    assert '`robots.txt` lists `/sitemap.xml`' in markdown
    assert '- [/articles/](/articles/)' in markdown
    assert 'X-Pathological-Date' in markdown and '/clock' in markdown and 'curl ' in markdown
    assert '| regulars | article | `/articles/<name>` |' in markdown


def test_readme_md_served_as_markdown(fetch):
    """/README.md is the Markdown as text/markdown."""
    response = fetch('/README.md', host='mirage')
    assert response.headers['content-type'] == 'text/markdown; charset=utf-8'
    assert response.body.decode() == readme_markdown(HOSTS['mirage'])


def test_render():
    """render handles headings, paragraphs, lists, tables, code spans, fenced code and links."""
    markdown = ('# Top\n\nOne line\nand more with `a<b`.\n\n## Sub\n\n- [Link](/x) item\n- plain\n\n'
                '| A | B |\n| --- | --- |\n| `/p` | q & r |\n\n```bash\ncurl https://x/<y>\n```\n')
    assert render(markdown) == (
        '<h1>Top</h1>\n<p>One line and more with <code>a&lt;b</code>.</p>\n<h2>Sub</h2>\n'
        '<ul>\n<li><a href="/x">Link</a> item</li>\n<li>plain</li>\n</ul>\n'
        '<table>\n<tr><th>A</th><th>B</th></tr>\n<tr><td><code>/p</code></td><td>q &amp; r</td></tr>\n</table>\n'
        '<pre><code>curl https://x/&lt;y&gt;</code></pre>')


_SERVES_ALL = 'The table lists every other URL that this host serves.'


def test_readme_table_intro_is_true_on_each_host():
    """yes-man and forwarding-address say what their paths answer; each other host says that it serves the table."""
    for name, host in HOSTS.items():
        markdown = readme_markdown(host)
        assert (_SERVES_ALL in markdown) == (name not in ('yes-man', 'forwarding-address')), name
    assert 'answers 200 with the HTML of the root page' in readme_markdown(HOSTS['yes-man']).split('## Time rules')[0]
    forwarding = readme_markdown(HOSTS['forwarding-address'])
    assert '301 to the same path on `librarian`' in forwarding.split('## All other URLs')[1]
    assert 'except `/README.md` and `/clock`' in forwarding


def test_readme_explains_the_rest_pattern():
    """The table intro explains both pattern forms."""
    assert 'ends in `...>` matches the rest of the path' in readme_markdown(HOSTS['librarian'])


@pytest.mark.parametrize('case', ['nested', 'after', 'no-namespace', 'latin1', 'gz', 'self', 'forms'])
def test_tipsy_readme_lists_each_robots_case(case):
    """The README of tipsy-cartographer names each value of ?case= with the sitemaps it lists."""
    markdown = readme_markdown(HOSTS['tipsy-cartographer'])
    assert f'`/robots.txt?case={case}`' in markdown


def test_readme_tags_column_hides_first():
    """No README shows the build-order tag first; the three public tags show."""
    for host in HOSTS.values():
        tag_cells = {row.rsplit('|', 2)[1].strip() for row in readme_markdown(host).split('## All other URLs')[1]
                     .split('## Time rules')[0].splitlines() if row.startswith('| ') and '`/' in row}
        tags = {tag for cell in tag_cells for tag in cell.split(', ') if tag}
        assert tags == {'own source', 'local only', 'production only'}, host.name


def test_readme_names_the_default_operator(fetch, monkeypatch):
    """With no operator variable, every host README names the default operator."""
    monkeypatch.delenv('PATHOLOGICAL_OPERATOR', raising=False)
    for name in HOSTS:
        markdown = fetch('/README.md', host=f'{name}.pathological.answersfrom.me').body.decode()
        assert 'This host is part of the pathological test site of Answers From Me, a web server' in markdown, name


@pytest.mark.parametrize('value', ['', '   '])
def test_readme_names_no_operator_when_blank(fetch, monkeypatch, value):
    """An empty or blank operator variable gives no name: only "the pathological test site"."""
    monkeypatch.setenv('PATHOLOGICAL_OPERATOR', value)
    html = fetch('/', host='breadcrumbs.pathological.answersfrom.me').body.decode()
    assert 'This host is part of the pathological test site, a web server' in html


def test_readme_names_the_operator(fetch, monkeypatch):
    """The operator variable puts its name in the introduction of each host README, escaped in the HTML."""
    monkeypatch.setenv('PATHOLOGICAL_OPERATOR', ' Example <Corp> ')
    for name in HOSTS:
        markdown = fetch('/README.md', host=f'{name}.pathological.answersfrom.me').body.decode()
        assert 'This host is part of the pathological test site of Example <Corp>, a web server' in markdown, name
    html = fetch('/', host='breadcrumbs.pathological.answersfrom.me').body.decode()
    assert 'the pathological test site of Example &lt;Corp&gt;, a web server' in html


def test_pages_fit_a_narrow_screen(fetch):
    """Each page has a viewport tag; a README page lets a wide table or code block scroll by itself."""
    article = fetch('/articles/starter', host='breadcrumbs.pathological.answersfrom.me').body.decode()
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in article
    assert '<style' not in article
    for host in ('breadcrumbs.pathological.answersfrom.me', 'pathological.answersfrom.me'):
        html = fetch('/', host=host).body.decode()
        assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in html
        assert 'table, pre {display: block; overflow-x: auto}' in html and 'th, td {padding:' in html
        assert fetch('/', host=host).headers['cache-control'] == 'no-cache'


def test_favicon_variable(fetch, monkeypatch):
    """With the favicon variable each README and the landing page link the icon; no other page does, nor without it."""
    monkeypatch.delenv('PATHOLOGICAL_FAVICON', raising=False)
    plain = fetch('/').body.decode()
    assert 'rel="icon"' not in plain and 'rel="icon"' not in fetch('/', host='localhost:8080').body.decode()
    monkeypatch.setenv('PATHOLOGICAL_FAVICON', ' https://example.com/i.png?a=1&b=2 ')
    link = '<link rel="icon" href="https://example.com/i.png?a=1&amp;b=2">'
    for host in ('breadcrumbs', 'janus', 'localhost:8080'):
        html = fetch('/', host=host).body.decode()
        assert html.count(link) == 1 and html.index(link) < html.index('</head>'), host
    assert fetch('/').body.decode().replace(link + '\n', '') == plain
    assert 'rel="icon"' not in fetch('/articles/starter').body.decode()
    assert 'rel="icon"' not in fetch('/README.md').body.decode()
