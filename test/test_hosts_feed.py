import json
import xml.etree.ElementTree as ET

import pytest

from afm_pathological.content import article
from afm_pathological.hosts import HOSTS

FEED_HOSTS = ('town-crier', 'headless-horseman', 'gutenberg', 'whisperer', 'masquerade')
ROOT_PATHS = {
    'town-crier': {'/robots.txt': 'text/plain', '/feed': 'application/rss+xml'},
    'headless-horseman': {'/robots.txt': 'text/plain', '/feed': 'application/rss+xml'},
    'gutenberg': {'/feed': 'application/rss+xml', '/wp-json/wp/v2/posts': 'application/json'},
    'whisperer': {'/robots.txt': 'text/plain', '/dispatches': 'application/rss+xml'},
    'masquerade': {'/index.xml': 'application/xml', '/feed': 'text/html'},
}


@pytest.mark.parametrize('name', FEED_HOSTS)
def test_root_urls(fetch, name):
    """Each feed host lists its root URLs, and each answers 200 with its content type."""
    assert {u.path: u.content_type for u in HOSTS[name].root_urls} == ROOT_PATHS[name]
    for path, content_type in ROOT_PATHS[name].items():
        response = fetch(path, host=name)
        assert response.status == 200, path
        assert response.headers['content-type'].split(';')[0] == content_type, path


@pytest.mark.parametrize('name', ['town-crier', 'headless-horseman', 'whisperer'])
def test_robots_disallow_all_with_no_sitemap(fetch, name):
    """robots.txt disallows all and has no Sitemap line."""
    assert fetch('/robots.txt', host=name).body.decode() == 'User-agent: *\nDisallow: /\n'


@pytest.mark.parametrize('name', ['town-crier', 'headless-horseman', 'gutenberg'])
def test_feed_path(fetch, name):
    """/feed is the daily feed with 10 entries."""
    assert len(ET.fromstring(fetch('/feed', host=name).body).findall('channel/item')) == 10


def test_undefined_feed_paths_stay_404(fetch):
    """A host-root feed path that a host does not define answers 404."""
    for name, path in (('breadcrumbs', '/feed'), ('whisperer', '/feed'), ('gutenberg', '/robots.txt'),
                       ('gutenberg', '/wp-json/wp/v2/pages'), ('town-crier', '/dispatches'),
                       ('town-crier', '/index.xml'), ('masquerade', '/robots.txt'), ('whisperer', '/rss.xml')):
        assert fetch(path, host=name).status == 404, (name, path)


def test_headless_horseman_refuses_head(fetch):
    """Each HEAD answers 405 with allow: GET, for a page, the root and the feed; GET is normal."""
    for path in ('/', '/articles/starter', '/feed', '/robots.txt', '/clock'):
        head = fetch(path, host='headless-horseman', method='HEAD')
        assert (head.status, head.headers['allow'], head.body) == (405, 'GET', b''), path
        assert fetch(path, host='headless-horseman').status == 200, path
    assert fetch('/feed', host='town-crier', method='HEAD').status == 200


def test_gutenberg_posts(fetch):
    """The WordPress endpoint lists the 10 daily pages as post objects, newest first."""
    posts = json.loads(fetch('/wp-json/wp/v2/posts', host='gutenberg').body)
    assert len(posts) == 10
    first = posts[0]
    assert first['link'] == 'https://gutenberg.pathological.answersfrom.me/daily/2026-11-25'
    assert first['date'] == '2026-11-25T06:00:00'
    assert first['title']['rendered'] == article('daily-2026-11-25').title
    assert first['excerpt']['rendered'].startswith('<p>') and isinstance(first['id'], int)
    assert [p['link'][-10:] for p in posts] == sorted((p['link'][-10:] for p in posts), reverse=True)


def test_head_elements_of_root_pages(fetch):
    """The root page of gutenberg and whisperer has its <head> element."""
    assert '<meta name="generator" content="WordPress 6.6">' in fetch('/', host='gutenberg').body.decode()
    link = '<link rel="alternate" type="application/rss+xml" href="/dispatches">'
    assert link in fetch('/', host='whisperer').body.decode()
    assert link not in fetch('/', host='town-crier').body.decode()


def test_masquerade_serves_the_root_page(fetch):
    """/index.xml and /feed return the HTML body of /; a matching conditional request gets 304, not an empty 200."""
    page = fetch('/', host='masquerade')
    for path in ('/index.xml', '/feed'):
        assert fetch(path, host='masquerade').body == page.body
        response = fetch(path, host='masquerade', headers={'if-none-match': page.headers['etag']})
        assert (response.status, response.body) == (304, b'')
        assert fetch(path, host='masquerade', headers={'if-none-match': '"x"'}).body == page.body
    assert fetch('/index.xml', host='masquerade').headers['content-type'] == 'application/xml'
    assert fetch('/feed', host='masquerade').headers['content-type'] == 'text/html'
    assert fetch('/index.xml', host='masquerade', method='HEAD').body == b''
