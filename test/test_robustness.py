import re
from datetime import date

import pytest

from afm_pathological.catalog import cases
from afm_pathological.clock import today
from afm_pathological.hosts import HOSTS
from afm_pathological.model import Request
from afm_pathological.site import respond
from conftest import NOW

_EXAMPLES = {'date': '2025-12-30', 'month': '2026-03', 'tokens...': 'a1/b2/'}


def _example(path: str) -> str:
    """A concrete path for a catalog path: each '<name>' segment replaced by an example value."""
    return re.sub(r'<([^>]+)>', lambda m: _EXAMPLES.get(m.group(1), '1'), path)


def _all_paths() -> list[str]:
    """Every catalog path (patterns as examples), the README paths, /clock and every root URL of every host."""
    paths = {_example(path) for case in cases() for path in case.paths}
    paths |= {url.path for host in HOSTS.values() for url in host.root_urls}
    return sorted(paths | {'/', '/README.md', '/clock'})


@pytest.mark.parametrize('value', ['0001-01-01', '2025-12-31', '9999-12-31', 'not-a-date'])
def test_no_date_header_breaks_any_path(value):
    """No X-Pathological-Date value makes any path of any host raise, for GET and HEAD."""
    for name in HOSTS:
        for path in _all_paths():
            for method in ('GET', 'HEAD'):
                respond(Request(f'{name}.pathological.answersfrom.me', path, method=method,
                                headers={'x-pathological-date': value}, now=NOW))


@pytest.mark.parametrize('value', ['0001-01-01', '2025-12-31', '9000-01-02', '9999-12-31', 'not-a-date'])
def test_unusable_date_header_is_ignored(value):
    """A header date before 2026-01-01 or after 9000-01-01 gives the date of the request, as an invalid one does."""
    assert today(Request('h', '/', headers={'x-pathological-date': value}, now=NOW)) == NOW.date()


def test_usable_date_header_limits():
    """2026-01-01 and 9000-01-01 are used."""
    for day in (date(2026, 1, 1), date(9000, 1, 1)):
        assert today(Request('h', '/', headers={'x-pathological-date': day.isoformat()}, now=NOW)) == day


@pytest.mark.parametrize('host, path, headers', [
    ('librarian.pathological.answersfrom.me', '/articles/starter', {}),
    ('librarian.pathological.answersfrom.me', '/sitemap.xml', {'if-modified-since': 'Fri, 01 Jan 2027 00:00:00 GMT'}),
    ('rip-van-winkle.pathological.answersfrom.me', '/articles/starter', {'if-none-match': '"x"'}),
    ('chicken-little.pathological.answersfrom.me', '/articles/starter', {'if-none-match': '"x"'}),
    ('breadcrumbs.pathological.answersfrom.me', '/missing', {}),
    ('breadcrumbs.pathological.answersfrom.me', '/potholes/status/500', {}),
    ('forwarding-address.pathological.answersfrom.me', '/x', {}),
    ('yes-man.pathological.answersfrom.me', '/anything', {}),
    ('sloth.pathological.answersfrom.me', '/robots.txt', {}),
    ('nobody.pathological.answersfrom.me', '/', {})])
@pytest.mark.parametrize('method', ['GET', 'HEAD'])
def test_every_response_says_noindex(host, path, headers, method):
    """Each response of each host, also 304, 404, 5xx, redirects and the unknown-host answer, has x-robots-tag."""
    response = respond(Request(host, path, method=method, headers=headers, now=NOW))
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'


def test_not_modified_says_noindex():
    """A 304 of the site also has x-robots-tag."""
    first = respond(Request('librarian.pathological.answersfrom.me', '/articles/starter', now=NOW))
    again = respond(Request('librarian.pathological.answersfrom.me', '/articles/starter',
                            headers={'if-none-match': first.headers['etag']}, now=NOW))
    assert again.status == 304 and again.headers['x-robots-tag'] == 'noindex, nofollow'
