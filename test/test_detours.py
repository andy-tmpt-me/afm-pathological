import re


def _links(response) -> list[str]:
    """The href of each <a> element of a response body."""
    return re.findall(r'<a href="([^"]*)"', response.body.decode())


def _words(response) -> int:
    """The number of words in the <p> elements of a response body."""
    return sum(len(re.sub(r'<[^>]+>', '', p).split()) for p in re.findall(r'<p>(.*?)</p>', response.body.decode()))


def test_section_links(fetch):
    """The section page links to the first page of each case, not to the targets."""
    response = fetch('/detours/')
    assert _links(response) == ['/detours/hop', '/detours/chain/1', '/detours/loop-a', '/detours/emigrant',
                                '/detours/refresh']
    assert _words(response) >= 250


def test_hop(fetch):
    """hop answers 301 to landed, which is an article."""
    response = fetch('/detours/hop')
    assert response.status == 301 and response.headers['location'] == '/detours/landed'
    assert _words(fetch('/detours/landed')) >= 250


def test_chain(fetch):
    """The chain is 301, 302, 307 and ends at landed-2, an article."""
    steps = [(fetch(f'/detours/chain/{i}').status, fetch(f'/detours/chain/{i}').headers['location']) for i in (1, 2, 3)]
    assert steps == [(301, '/detours/chain/2'), (302, '/detours/chain/3'), (307, '/detours/landed-2')]
    assert _words(fetch('/detours/landed-2')) >= 250
    assert fetch('/detours/chain/4').status == 404


def test_loop(fetch):
    """loop-a and loop-b answer 302 to each other."""
    assert (fetch('/detours/loop-a').status, fetch('/detours/loop-a').headers['location']) == (302, '/detours/loop-b')
    assert (fetch('/detours/loop-b').status, fetch('/detours/loop-b').headers['location']) == (302, '/detours/loop-a')


def test_emigrant(fetch):
    """emigrant answers 301 to librarian on the rest of the request host, with the request scheme."""
    response = fetch('/detours/emigrant')
    assert response.status == 301
    assert response.headers['location'] == 'https://librarian.pathological.answersfrom.me/articles/starter'
    www = fetch('/detours/emigrant', host='WWW.breadcrumbs.pathological.answersfrom.me')
    assert www.headers['location'] == 'https://librarian.pathological.answersfrom.me/articles/starter'


def test_refresh(fetch):
    """refresh is 200 with a meta refresh element and the text Redirecting; the target is an article."""
    response = fetch('/detours/refresh')
    body = response.body.decode()
    assert response.status == 200 and '<meta http-equiv="refresh" content="0; url=/detours/refreshed">' in body
    assert '<p>Redirecting</p>' in body
    assert _words(fetch('/detours/refreshed')) >= 250
