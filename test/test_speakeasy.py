import re
from datetime import timedelta

from afm_pathological.clock import EPOCH

LOGIN = 'https://breadcrumbs.pathological.answersfrom.me/speakeasy/login'


def _on(n: int) -> dict[str, str]:
    """The header that sets the day number to n."""
    return {'x-pathological-date': (EPOCH + timedelta(days=n)).isoformat()}


def _links(response) -> list[str]:
    """The href of each <a> element of a response body."""
    return re.findall(r'<a href="([^"]*)"', response.body.decode())


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def test_section_links(fetch):
    """The section page links to the case pages, not to the login page."""
    response = fetch('/speakeasy/')
    assert _links(response) == ['/speakeasy/members/1', '/speakeasy/members/2', '/speakeasy/members/3',
                                '/speakeasy/gate', '/speakeasy/teaser', '/speakeasy/turncoat', '/speakeasy/reformed']
    assert _words(response) >= 250


def test_login_page(fetch):
    """The login page has a password input and a canonical link on its own absolute URL."""
    response = fetch('/speakeasy/login')
    body = response.body.decode()
    assert response.status == 200 and '<input type="password"' in body
    assert f'<link rel="canonical" href="{LOGIN}">' in body


def test_members_redirect(fetch):
    """members/1, 2 and 3 answer 302 to the login page."""
    for i in (1, 2, 3):
        response = fetch(f'/speakeasy/members/{i}')
        assert response.status == 302 and response.headers['location'] == '/speakeasy/login'
    assert fetch('/speakeasy/members/4').status == 404


def test_gate(fetch):
    """gate is 200 with a password input and its own text, and no redirect."""
    response = fetch('/speakeasy/gate')
    assert response.status == 200 and 'type="password"' in response.body.decode()
    assert _words(response) >= 250 and 'rel="canonical"' not in response.body.decode()


def test_teaser(fetch):
    """The teaser has two article paragraphs, then the members-only paragraph, and no password input."""
    response = fetch('/speakeasy/teaser')
    paragraphs = re.findall(r'<p>(.*?)</p>', response.body.decode())
    assert response.status == 200 and len(paragraphs) == 3
    assert paragraphs[2] == 'This article is for members only.'
    assert 'password' not in response.body.decode()


def test_turncoat_and_reformed(fetch):
    """turncoat is open when N mod 14 is below 7, else 302 to the login page; reformed is the reverse."""
    for n, open_ in ((0, True), (6, True), (7, False), (13, False), (14, True)):
        turncoat, reformed = fetch('/speakeasy/turncoat', headers=_on(n)), fetch('/speakeasy/reformed', headers=_on(n))
        assert (turncoat.status, reformed.status) == ((200, 302) if open_ else (302, 200)), n
        walled = reformed if open_ else turncoat
        assert walled.headers['location'] == '/speakeasy/login'
        assert _words(reformed if not open_ else turncoat) >= 250


def test_login_canonical_is_escaped(fetch):
    """A host with a quote stays inside the href of the canonical link."""
    body = fetch('/speakeasy/login', host='breadcrumbs.a"b&c').body.decode()
    assert '<link rel="canonical" href="https://breadcrumbs.a&quot;b&amp;c/speakeasy/login">' in body
