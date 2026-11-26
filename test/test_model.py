import pytest

from afm_pathological.model import Request


@pytest.mark.parametrize('host, scheme, expected', [
    ('breadcrumbs.pathological.answersfrom.me', 'https', 'https://librarian.pathological.answersfrom.me/a'),
    ('www.janus.pathological.answersfrom.me', 'https', 'https://librarian.pathological.answersfrom.me/a'),
    ('Breadcrumbs.Localhost:8080', 'http', 'http://librarian.localhost:8080/a'),
    ('www.breadcrumbs.localhost:8080', 'http', 'http://librarian.localhost:8080/a'),
    ('breadcrumbs', 'https', 'https://librarian/a'),
    ('breadcrumbs:8080', 'http', 'http://librarian:8080/a')])
def test_sibling_url(host, scheme, expected):
    """The first label after an optional www. is replaced; the scheme, the rest and the port stay."""
    assert Request(host, '/x', scheme=scheme).sibling_url('librarian', '/a') == expected


def test_sibling_url_uses_the_host_override():
    """The x-pathological-host header replaces the Host header, as in each other URL of the site."""
    request = Request('localhost:8080', '/x', headers={'x-pathological-host': 'janus.localhost:8080'}, scheme='http')
    assert request.sibling_url('librarian', '/a') == 'http://librarian.localhost:8080/a'
