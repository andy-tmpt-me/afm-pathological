import hashlib
import json
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from afm_pathological import catalog, readme
from afm_pathological.clock import EPOCH, day_number, http_date, today
from afm_pathological.hosts import HOSTS, HostSpec, is_host_root, resolve
from afm_pathological.model import Request, Response
from afm_pathological.pages import page
from afm_pathological.responses import html, not_found, text


def _clock(request: Request) -> Response:
    """The time, the date in effect and the day number that the site uses."""
    body = {'utc': request.now.astimezone(timezone.utc).isoformat(), 'date': today(request).isoformat(),
            'day_number': day_number(request)}
    response = text(json.dumps(body), content_type='application/json')
    response.validators = False
    return response


# On a narrow screen a wide table or code block scrolls by itself, not the whole page
_NARROW_STYLE = '<style>table, pre {display: block; overflow-x: auto}</style>\n'


def _markdown_page(markdown: str, path: str, head_html: str = '', lead_html: str = '') -> Response:
    """A README: HTML at / and Markdown at /README.md; the HTML has lead_html under its heading."""
    if path == '/README.md':
        return text(markdown, content_type='text/markdown; charset=utf-8')
    heading, _, rest = markdown.partition('\n')
    # no-cache: a browser asks again each time, so a person sees a new README right after a deploy
    return html(page(heading.removeprefix('# '), lead_html + readme.render(rest.strip('\n')),
                     readme.favicon_html() + _NARROW_STYLE + head_html),
                headers={'cache-control': 'no-cache'})


def _unknown_host() -> Response:
    """404 with the list of host names."""
    response = text('Unknown host. The hosts are:\n' + '\n'.join(HOSTS) + '\n', status=404)
    response.validators = False
    return response


# A robot can read the landing page, the image of its link preview and nothing else: the longest rule that matches
# a path wins, `$` ends a path
_LANDING_ROBOTS = f'User-agent: *\nAllow: /$\nAllow: {readme.PREVIEW_IMAGE_PATH}$\nDisallow: /\n'
_PREVIEW_IMAGE = Path(__file__).with_name('preview.jpg').read_bytes()


def _landing(request: Request) -> Response:
    """The answer for the site domain, a Host that names no host: the landing page, /clock and robots.txt."""
    if request.path in ('/', '/README.md'):
        domain = request.host.lower().removeprefix('www.')
        response = _markdown_page(readme.landing_markdown(request.scheme, domain), request.path,
                                  readme.preview_html(request.scheme, domain), readme.preview_image_html())
        if request.path == '/':  # the one page that a search engine can list; its links are not for a robot
            response.headers['x-robots-tag'] = 'nofollow'
        return response
    if request.path == '/clock':
        return _clock(request)
    if request.path == readme.PREVIEW_IMAGE_PATH:
        return Response(200, {'content-type': 'image/jpeg'}, _PREVIEW_IMAGE)
    return text(_LANDING_ROBOTS) if request.path == '/robots.txt' else _unknown_host()


def _answer(host: HostSpec, request: Request) -> Response:
    """The response of the host before finish."""
    if host.before and (response := host.before(request)):
        return response
    if request.path == '/clock':
        return _clock(request)
    if request.path in ('/', '/README.md'):
        return _markdown_page(readme.readme_markdown(host), request.path, host.head_html)
    if host.root and (response := host.root(request)):
        return response
    if is_host_root(request.path):
        return not_found()
    case = catalog.find(request.path)
    return (case.handler(request) if case else None) or not_found()


def _not_modified(request: Request, etag: str, last_modified: str) -> bool:
    """True when the conditional headers of the request match the validators."""
    if 'if-none-match' in request.headers:
        return request.headers['if-none-match'] == etag
    try:
        return parsedate_to_datetime(request.headers['if-modified-since']) >= parsedate_to_datetime(last_modified)
    except (KeyError, TypeError, ValueError):
        return False


def finish(request: Request, response: Response) -> Response:
    """Add validators, answer 304 to a matching conditional request, set content-length and strip HEAD bodies."""
    response.headers.setdefault('x-robots-tag', 'noindex, nofollow')  # no host belongs in a search engine
    if response.validators and response.status == 200:
        etag = response.headers.setdefault('etag', f'"{hashlib.sha256(response.body).hexdigest()[:20]}"')
        last_modified = response.headers.setdefault('last-modified', http_date(EPOCH))
        if _not_modified(request, etag, last_modified):
            response.headers.pop('content-length', None)
            response.status, response.body = 304, b''
            return response
    response.headers['content-length'] = str(len(response.body))
    if request.method == 'HEAD':
        response.body = b''
    return response


def respond(request: Request) -> Response:
    """The response of the site to one request."""
    host, _ = resolve(request.host_header)
    if host is None:  # an unknown X-Pathological-Host value is a mistake of the client, not the site domain
        return finish(request, _unknown_host() if request.headers.get('x-pathological-host') else _landing(request))
    response = finish(request, _answer(host, request))
    return host.after(request, response) if host.after else response
