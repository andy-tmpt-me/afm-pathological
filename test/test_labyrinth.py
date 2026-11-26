import re
from datetime import datetime, timezone

from afm_pathological.catalog import cases, find
from afm_pathological.model import Request
from afm_pathological.site import respond

HOST = 'breadcrumbs.pathological.answersfrom.me'


def _links(response) -> list[str]:
    """The href of each <a> element of a response body, in order."""
    return [h.replace('&amp;', '&') for h in re.findall(r'<a href="([^"]*)"', response.body.decode())]


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def _title(response) -> str:
    """The <title> of a response body."""
    return re.search(r'<title>(.*?)</title>', response.body.decode()).group(1)


def test_no_section_page(fetch):
    """The labyrinth has no section page: each case is its own source, and each carries the own source tag."""
    assert fetch('/labyrinth/').status == 404
    assert all(c.tags == ('own source',) for c in cases() if c.family == 'labyrinth')


def test_calendar_start(fetch):
    """/labyrinth/calendar/ links to the page of the month of the request date."""
    response = fetch('/labyrinth/calendar/')
    assert response.status == 200 and _words(response) >= 250
    assert _links(response) == ['/labyrinth/calendar/2026-11']
    moved = fetch('/labyrinth/calendar/', headers={'x-pathological-date': '2027-01-15'})
    assert _links(moved) == ['/labyrinth/calendar/2027-01']


def test_calendar_month_links(fetch):
    """A month page links to the month before and after, across year ends; each month is its own article."""
    assert _links(fetch('/labyrinth/calendar/2026-11')) == ['/labyrinth/calendar/2026-10',
                                                            '/labyrinth/calendar/2026-12']
    assert _links(fetch('/labyrinth/calendar/2026-12')) == ['/labyrinth/calendar/2026-11',
                                                            '/labyrinth/calendar/2027-01']
    assert _links(fetch('/labyrinth/calendar/2027-01'))[0] == '/labyrinth/calendar/2026-12'
    assert _title(fetch('/labyrinth/calendar/2026-10')) != _title(fetch('/labyrinth/calendar/2026-12'))
    assert _words(fetch('/labyrinth/calendar/2026-10')) >= 250


def test_calendar_limit(fetch):
    """A month 24 months from the request month answers 200; 25 months or an invalid month answers 404."""
    assert fetch('/labyrinth/calendar/2028-11').status == 200
    assert fetch('/labyrinth/calendar/2024-11').status == 200
    assert fetch('/labyrinth/calendar/2028-12').status == 404
    assert fetch('/labyrinth/calendar/2024-10').status == 404
    for bad in ('2026-13', '2026-00', '2026-1', 'x', '2026-11-01'):
        assert fetch(f'/labyrinth/calendar/{bad}').status == 404, bad


def test_session_tokens(fetch):
    """Each session page has five links that extend its path by a token; tokens come from the time and number."""
    now = datetime(2026, 11, 25, 12, 0, 45, 123456, tzinfo=timezone.utc)
    first = fetch('/labyrinth/session/', now=now)
    links = _links(first)
    assert len(links) == len(set(links)) == 5
    assert all(re.fullmatch(r'/labyrinth/session/[0-9a-f]+/', link) for link in links)
    assert _links(fetch('/labyrinth/session/', now=now)) == links
    assert _links(fetch('/labyrinth/session/', now=now.replace(microsecond=1))) != links
    child = fetch(links[0], now=now)
    assert [link.startswith(links[0]) and link != links[0] for link in _links(child)] == [True] * 5
    assert _title(child) == _title(first) and _words(first) >= 250
    assert re.sub(r'<ul>.*</ul>', '', child.body.decode(), flags=re.S) == re.sub(
        r'<ul>.*</ul>', '', first.body.decode(), flags=re.S)


def test_session_depth_limit(fetch):
    """A path with 24 token segments answers 200 and one with 25 answers 404."""
    assert fetch('/labyrinth/session/' + 'a1/' * 24).status == 200
    assert fetch('/labyrinth/session/' + 'a1/' * 25).status == 404


def test_session_follow_to_the_limit(fetch):
    """Following the first link of each page ends in a 404 after 24 steps."""
    path, steps = '/labyrinth/session/', 0
    while (response := fetch(path)).status == 200:
        path, steps = _links(response)[0], steps + 1
    assert steps == 25 and response.status == 404


def test_shop(fetch):
    """shop links to the 8 combinations of color, size and sort; each query answers the same page."""
    response = fetch('/labyrinth/shop')
    links = _links(response)
    assert len(links) == len(set(links)) == 8
    assert '/labyrinth/shop?color=red&size=s&sort=new' in links
    assert '/labyrinth/shop?color=blue&size=m&sort=old' in links
    for link in links:
        path, _, query = link.partition('?')
        assert respond(Request(host=HOST, path=path, query=query)).body == response.body
    assert _words(response) >= 250


def test_session_is_one_pattern_path():
    """The session case has one path, a pattern that matches the rest of the path."""
    session = next(case for case in cases() if case.name == 'session-path')
    assert session.paths == ('/labyrinth/session/<tokens...>',)
    for path in ('/labyrinth/session/', '/labyrinth/session/a1/', '/labyrinth/session/' + 'a1/' * 30,
                 '/labyrinth/session/a1', '/labyrinth/session/a1//'):
        assert find(path) is session, path


def test_session_refuses_odd_paths(fetch):
    """A path with no final slash, an empty token or more than 24 tokens answers 404."""
    for path in ('/labyrinth/session/a1', '/labyrinth/session/a1/b2', '/labyrinth/session/a1//',
                 '/labyrinth/session//', '/labyrinth/session/' + 'a1/' * 25):
        assert fetch(path).status == 404, path
    assert fetch('/labyrinth/session/a1/b2/').status == 200


def test_session_has_one_readme_row(fetch):
    """The README lists the session case in one row."""
    markdown = fetch('/README.md').body.decode()
    assert len([line for line in markdown.splitlines() if line.startswith('| labyrinth | session-path |')]) == 1
