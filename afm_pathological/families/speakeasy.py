from html import escape

from afm_pathological.catalog import Case, section_case
from afm_pathological.clock import day_number
from afm_pathological.content import article
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_body, article_page, page
from afm_pathological.responses import html, redirect

LOGIN = '/speakeasy/login'
FORM = ('<form method="post" action="/speakeasy/login">\n<label>Password <input type="password" name="password">'
        '</label>\n<button type="submit">Sign in</button>\n</form>')


def _login(request: Request) -> Response:
    """The login page: a password field and a canonical link on its own absolute URL."""
    head = f'<link rel="canonical" href="{escape(request.url(LOGIN), quote=True)}">'
    return html(page('Sign in to the sourdough club', FORM, head))


def _gate(request: Request) -> Response:
    """An article text followed by a password field, with no redirect."""
    a = article('gate')
    return html(page(a.title, article_body(a) + '\n' + FORM))


def _teaser(request: Request) -> Response:
    """Two paragraphs of an article, then the members-only line."""
    a = article('teaser')
    return html(page(a.title, '\n'.join(f'<p>{p}</p>' for p in a.paragraphs[:2]) +
                     '\n<p>This article is for members only.</p>'))


def _wall(request: Request, open_when_present: bool) -> Response:
    """An article in the first 7 days of each 14 (the last 7 when reversed), else a 302 to the login page."""
    if (day_number(request) % 14 < 7) == open_when_present:
        return html(article_page(request.path.removeprefix('/speakeasy/')))
    return redirect(LOGIN, 302)


CASES: list[Case] = [
    Case('speakeasy', 'redirect-to-login', ('/speakeasy/members/1', LOGIN),
         '302 to /speakeasy/login, a page with a password field and a canonical link on itself',
         lambda request: _login(request) if request.path == LOGIN else redirect(LOGIN, 302), ('first',)),
    Case('speakeasy', 'password-field', ('/speakeasy/gate',), '200 with a password field and no redirect', _gate),
    Case('speakeasy', 'shared-canonical', ('/speakeasy/members/2', '/speakeasy/members/3'),
         'Each answers 302 to the login page', lambda request: redirect(LOGIN, 302)),
    Case('speakeasy', 'teaser', ('/speakeasy/teaser',),
         'Two paragraphs, then "This article is for members only"; no redirect, no password field', _teaser),
    Case('speakeasy', 'wall-added-later', ('/speakeasy/turncoat', '/speakeasy/reformed'),
         'turncoat is open when N mod 14 is below 7 and answers 302 to the login page after; reformed is the reverse',
         lambda request: _wall(request, request.path.endswith('turncoat'))),
    section_case('speakeasy', 'Speakeasy: sourdough pages behind a login wall', [
        '/speakeasy/members/1', '/speakeasy/members/2', '/speakeasy/members/3', '/speakeasy/gate',
        '/speakeasy/teaser', '/speakeasy/turncoat', '/speakeasy/reformed']),
]
