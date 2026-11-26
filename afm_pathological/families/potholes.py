from typing import Callable, Optional

from afm_pathological.catalog import Case, section_case
from afm_pathological.clock import in_error_slot
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_page, page
from afm_pathological.responses import html

STATUSES = (403, 404, 410, 429, 500, 503)
# The Brotli encoding of a short HTML page ("This page was compressed with Brotli."), made once with the brotli
# command. The first bytes are not valid UTF-8, so a reader that does not decode the body fails on it.
_BROTLI = (
    b'\x1f\x86\x00@\xc5ml]\xd7\x08\x87k\x07\x15\x04E\xa4\x93\xd3\x83\xfa\x0b\x03\n\x03k\xcb_\xb9\x8d\xad-\xa2y#'
    b'\xe9\x05\x04\xc3a\xe8\xa9\x9b\xefB\xdbpxFB\x89l\x13(M\xd1\x96\xb3a\xf8\xf7\x01E\xff\xccN\xd3\xcdwuY8\\\x00')
CHALLENGE = page('Just a moment...', '<p>Checking your browser before you visit the site.</p>\n'
                 '<div id="cf-chl-widget"></div>')


def _plain(response: Response, **headers: str) -> Response:
    """The response with the given headers and no validators of the site."""
    response.validators = False
    response.headers.update(headers)
    return response


def _article(name: str, content_type: str = 'text/html; charset=utf-8') -> Response:
    """The article of a pothole path with the given content type."""
    return Response(200, {'content-type': content_type}, article_page(f'potholes-{name}').encode())


def _status(request: Request) -> Response:
    """The status of the path, with a short HTML body."""
    code = int(request.path.rsplit('/', 1)[1])
    return _plain(html(f'<p>Status {code}.</p>', code), **({'retry-after': '30'} if code == 429 else {}))


def _soft_404(request: Request) -> Response:
    """200 with the title 'Page not found' and one sentence."""
    return html(page('Page not found', '<p>Sorry, this page could not be found.</p>'))


def _fails_first(request: Request) -> Response:
    """503 in seconds 0 to 29 of the minute, an article in seconds 30 to 59."""
    return _plain(html('<p>Unavailable.</p>', 503)) if in_error_slot(request) else html(article_page('fails-first'))


def _slow_get(request: Request) -> Response:
    """An article whose first byte comes after 35 s; a HEAD answers at once."""
    response = html(article_page('slow-get'))
    response.delay_sec = 35 if request.method == 'GET' else 0
    return response


def _slow_head(request: Request) -> Response:
    """An article; a HEAD waits 12 s."""
    response = html(article_page('slow-head'))
    response.delay_sec = 12 if request.method == 'HEAD' else 0
    return response


def _torn(request: Request) -> Response:
    """An article padded to exactly 10,000 bytes; the connection closes after 2,000."""
    body = article_page('torn')
    padding = 10000 - len(body.encode()) - len('<!--  -->\n')
    response = html(body.replace('</body>', f'<!-- {"x" * padding} -->\n</body>'))
    response.tear_after = 2000
    return response


def _latin1(request: Request) -> Response:
    """A page with the word café in Latin-1 under a utf-8 header."""
    body = page('Sourdough baking notes: latin1', '<p>The café bakes sourdough bread each morning.</p>')
    return Response(200, {'content-type': 'text/html; charset=utf-8'}, body.encode('latin-1'))


def _bad_date(request: Request) -> Response:
    """An article whose Last-Modified is an ISO timestamp, not an HTTP date."""
    return _plain(html(article_page('bad-date')), **{'last-modified': '2026-11-25T00:00:00Z'})


def _wrong_encoding(request: Request) -> Response:
    """A body that does not match its Content-Encoding: real Brotli under br, plain text under gzip."""
    brotli = request.path.endswith('brotli')
    return Response(200, {'content-type': 'text/html; charset=utf-8', 'content-encoding': 'br' if brotli else 'gzip'},
                    _BROTLI if brotli else article_page('not-gzip').encode())


def _case(name: str, behavior: str, handler: Callable[[Request], Optional[Response]], *tags: str,
          paths: tuple[str, ...]) -> Case:
    """A potholes case."""
    return Case('potholes', name, paths, behavior, handler, tags)


CASES: list[Case] = [
    section_case('potholes', 'Potholes: errors and broken responses', [
        *(f'/potholes/status/{code}' for code in STATUSES), '/potholes/soft-404', '/potholes/fails-first',
        '/potholes/slow-get', '/potholes/slow-head', '/potholes/torn', '/potholes/empty', '/potholes/xml-typed',
        '/potholes/fake.pdf', '/potholes/fake.mp3', '/potholes/challenge.mp3', '/potholes/blob.xyz',
        '/potholes/latin1', '/potholes/bad-date', '/potholes/brotli', '/potholes/not-gzip']),
    _case('status', 'The status of the path; 429 has Retry-After: 30', _status,
          paths=tuple(f'/potholes/status/{code}' for code in STATUSES)),
    _case('soft-404', '200 with the title "Page not found" and one sentence', _soft_404, paths=('/potholes/soft-404',)),
    _case('fails-first', '503 in seconds 0 to 29 of each minute, 200 in seconds 30 to 59', _fails_first,
          'local only', paths=('/potholes/fails-first',)),
    _case('slow', 'slow-get sends its first byte after 35 s and answers a HEAD at once; slow-head answers a HEAD '
          'after 12 s and a GET at once',
          lambda request: _slow_get(request) if request.path.endswith('get') else _slow_head(request), 'local only',
          paths=('/potholes/slow-get', '/potholes/slow-head')),
    _case('torn-body', 'The Content-Length is 10,000; the connection closes after 2,000 bytes. A proxy that '
          'buffers responses, as the demo site has, answers 502 instead', _torn,
          paths=('/potholes/torn',)),
    _case('empty-body', '200, text/html, no body',
          lambda request: _plain(Response(200, {'content-type': 'text/html; charset=utf-8'})),
          paths=('/potholes/empty',)),
    _case('xml-typed', 'An HTML article sent as application/xml',
          lambda request: _article('xml-typed', 'application/xml'), paths=('/potholes/xml-typed',)),
    _case('fake-pdf', 'An HTML page at a .pdf URL', lambda request: _article('fake-pdf'),
          paths=('/potholes/fake.pdf',)),
    _case('fake-media', 'An HTML page at an .mp3 URL; challenge.mp3 has the title "Just a moment..." and cf-chl',
          lambda request: html(CHALLENGE) if request.path.endswith('challenge.mp3') else _article('fake-mp3'),
          paths=('/potholes/fake.mp3', '/potholes/challenge.mp3')),
    _case('unknown-type', 'application/x-unknown, 1,024 bytes of a fixed pattern',
          lambda request: Response(200, {'content-type': 'application/x-unknown'}, bytes(range(256)) * 4),
          paths=('/potholes/blob.xyz',)),
    _case('wrong-charset', 'The header says charset=utf-8; the body is Latin-1 with the word café', _latin1,
          paths=('/potholes/latin1',)),
    _case('bad-validator', 'Last-Modified: 2026-11-25T00:00:00Z, which is not an HTTP date', _bad_date,
          paths=('/potholes/bad-date',)),
    _case('wrong-encoding', 'brotli sends Brotli bytes with Content-Encoding: br; not-gzip sends plain text with '
          'Content-Encoding: gzip', _wrong_encoding,
          paths=('/potholes/brotli', '/potholes/not-gzip')),
]
