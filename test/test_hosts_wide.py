from urllib.parse import urlsplit

import pytest

from afm_pathological.hosts import HOSTS
from afm_pathological.model import Request
from afm_pathological.site import respond

CHROME = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


@pytest.mark.parametrize('method', ['GET', 'HEAD'])
@pytest.mark.parametrize('path', ['/robots.txt', '/feed', '/wp-json/wp/v2/posts', '/anything', '/sitemap.xml'])
def test_yes_man_answers_everything(fetch, path, method):
    """Each path answers 200 text/html with the length of the root page, for GET and HEAD."""
    root = fetch('/', host='yes-man')
    response = fetch(path, host='yes-man', method=method)
    assert response.status == 200
    assert response.headers['content-type'].startswith('text/html')
    assert response.headers['content-length'] == str(len(root.body))
    assert response.body == (root.body if method == 'GET' else b'')


def test_yes_man_keeps_clock_and_readme(fetch):
    """/clock and /README.md are not the root page; a conditional request gets the page, not a 304 loop."""
    assert fetch('/clock', host='yes-man').headers['content-type'] == 'application/json'
    assert fetch('/README.md', host='yes-man').headers['content-type'].startswith('text/markdown')
    assert fetch('/x', host='yes-man', headers={'if-none-match': '"y"'}).status == 200


def test_sloth_delays(fetch):
    """robots.txt waits 15 s, each HEAD 12 s and each other response 2 s."""
    robots = fetch('/robots.txt', host='sloth')
    assert robots.body.decode() == 'User-agent: *\nDisallow: /\n'
    assert robots.delay_sec == 15
    assert fetch('/articles/starter', host='sloth', method='HEAD').delay_sec == 12
    assert fetch('/articles/starter', host='sloth').delay_sec == 2
    assert fetch('/', host='sloth').delay_sec == 2
    assert fetch('/missing', host='sloth').delay_sec == 2
    assert fetch('/articles/starter', host='breadcrumbs').delay_sec == 0


def test_sloth_keeps_a_longer_delay_of_a_case(fetch):
    """sloth uses the larger of its own delay and the delay of the case."""
    assert fetch('/potholes/slow-get', host='sloth').delay_sec == 35
    assert fetch('/potholes/slow-get', host='sloth', method='HEAD').delay_sec == 12
    assert fetch('/potholes/slow-head', host='sloth').delay_sec == 2


@pytest.mark.parametrize('host, target', [
    ('forwarding-address.pathological.answersfrom.me', 'https://librarian.pathological.answersfrom.me'),
    ('forwarding-address.localhost:8080', 'https://librarian.localhost:8080'),
    ('FORWARDING-ADDRESS.localhost', 'https://librarian.localhost'),
    ('www.forwarding-address.localhost:8080', 'https://librarian.localhost:8080')])
def test_forwarding_address(fetch, host, target):
    """Each path answers 301 to the same path on librarian, with the query."""
    for path in ('/', '/robots.txt', '/sitemap.xml', '/articles/starter'):
        response = fetch(path, host=host)
        assert response.status == 301 and response.headers['location'] == target + path
    response = respond(Request(host, '/daily/', query='a=1&b=2'))
    assert response.headers['location'] == f'{target}/daily/?a=1&b=2'
    assert urlsplit(response.headers['location']).netloc == target.removeprefix('https://')


def test_forwarding_address_scheme_head_and_exceptions(fetch):
    """The scheme is kept, HEAD redirects, and /README.md and /clock answer themselves."""
    response = respond(Request('forwarding-address.localhost:8080', '/x', scheme='http'))
    assert response.headers['location'] == 'http://librarian.localhost:8080/x'
    assert fetch('/x', host='forwarding-address', method='HEAD').status == 301
    readme = fetch('/README.md', host='forwarding-address')
    assert readme.status == 200 and readme.headers['content-type'].startswith('text/markdown')
    assert fetch('/clock', host='forwarding-address').status == 200


def test_doorman(fetch):
    """The Chrome 120 user agent gets 403 for each path and method; any other request is normal."""
    chrome = {'user-agent': CHROME}
    for path in ('/', '/robots.txt', '/articles/starter', '/README.md'):
        for method in ('GET', 'HEAD'):
            response = fetch(path, host='doorman', method=method, headers=chrome)
            assert response.status == 403 and response.headers['content-type'].startswith('text/html')
            assert fetch(path, host='doorman', method=method, headers={'user-agent': 'curl/8.0'}).status == 200
            assert fetch(path, host='doorman', method=method).status == 200
    assert fetch('/articles/starter', host='doorman', headers=chrome).body
    assert fetch('/robots.txt', host='doorman').body.decode() == 'User-agent: *\nDisallow: /\n'
    assert fetch('/articles/starter', host='breadcrumbs', headers=chrome).status == 200


def test_root_urls_of_wide_hosts():
    """yes-man lists its five root URLs with 200, forwarding-address lists two with 301, doorman and sloth one."""
    assert {u.path: (u.status, u.content_type) for u in HOSTS['yes-man'].root_urls} == {
        path: (200, 'text/html') for path in ('/robots.txt', '/feed', '/index.xml', '/sitemap.xml',
                                              '/wp-json/wp/v2/posts')}
    forwarding = [(u.path, u.status) for u in HOSTS['forwarding-address'].root_urls]
    assert forwarding == [('/robots.txt', 301), ('/sitemap.xml', 301)]
    assert [u.path for u in HOSTS['doorman'].root_urls] == ['/robots.txt']
    assert [u.path for u in HOSTS['sloth'].root_urls] == ['/robots.txt']


def test_readme_states_what_other_root_urls_answer(fetch):
    """The README of yes-man and forwarding-address does not say that an unlisted root URL answers 404."""
    for name in ('yes-man', 'forwarding-address'):
        markdown = fetch('/README.md', host=name).body.decode().split('## Start here')[0]
        assert 'answers 404' not in markdown
    assert 'answers 404' in fetch('/README.md', host='doorman').body.decode()


def test_librarian_links_from_the_www_name(fetch):
    """On www.janus each link, canonical and redirect to librarian names the librarian host of the same domain."""
    host, target = 'www.janus.pathological.answersfrom.me', 'https://librarian.pathological.answersfrom.me'
    assert f'href="{target}/articles/starter"' in fetch('/tangle/other-host', host=host).body.decode()
    canonical = f'<link rel="canonical" href="{target}/articles/starter">'
    assert canonical in fetch('/doppelgangers/canon-host', host=host).body.decode()
    assert fetch('/detours/emigrant', host=host).headers['location'] == f'{target}/articles/starter'
    assert fetch('/x', host='www.forwarding-address.pathological.answersfrom.me').headers['location'] == f'{target}/x'


def test_sloth_and_forwarding_address_say_what_the_spec_says():
    """The host-root cells of sloth and forwarding-address are the texts of the spec."""
    assert HOSTS['sloth'].root_says == (
        '`robots.txt`, with no `Sitemap:` line, answers after 15 s. Each HEAD answers after 12 s. Each other response '
        'answers after 2 s. A longer delay of a case stays: `/potholes/slow-get` answers a GET after 35 s')
    assert HOSTS['forwarding-address'].root_says == (
        'Each path except `/README.md` and `/clock`, also `/robots.txt`, answers 301 to the same path on `librarian`')
