import json
from html import escape
from typing import Optional

from afm_pathological.catalog import Case, section_case
from afm_pathological.content import article
from afm_pathological.model import Request, Response
from afm_pathological.pages import article_page, page
from afm_pathological.responses import html

_SHORT_WORDS = 150
_CHILDREN = ('1', '2', '3')


def _shell(key: str) -> str:
    """A page whose body is an empty container and a script that writes the article into it."""
    a = article(key)
    body = ''.join(f'<p>{escape(p)}</p>' for p in a.paragraphs)
    script = f'document.getElementById("app").innerHTML = {json.dumps(body).replace("</", "<\\/")};'
    return page(a.title, f'<div id="app"></div>\n<script>\n{script}\n</script>')


def _short(request: Request) -> Response:
    """An article cut to 150 words."""
    a = article('holograms-short')
    words = ' '.join(a.paragraphs).split()[:_SHORT_WORDS]
    return html(page(a.title, f'<p>{escape(" ".join(words))}</p>'))


def _script_links(request: Request) -> Optional[Response]:
    """A long server-rendered page with a script that adds three links, and the three articles."""
    number = request.path.removeprefix('/holograms/script-links/')
    if number in _CHILDREN:
        return html(article_page(f'holograms-script-links-{number}'))
    if number:
        return None
    script = ('var list = document.createElement("ul");\n'
              f'for (var href of {json.dumps([f"/holograms/script-links/{n}" for n in _CHILDREN])}) {{\n'
              '  var item = document.createElement("li");\n'
              '  var link = document.createElement("a");\n'
              '  link.href = href;\n'
              '  link.textContent = "Article " + href.slice(-1);\n'
              '  item.appendChild(link);\n'
              '  list.appendChild(item);\n'
              '}\n'
              'document.body.appendChild(list);')
    return html(article_page('holograms-script-links').replace('</body>', f'<script>\n{script}\n</script>\n</body>'))


def _mixed(request: Request) -> Optional[Response]:
    """A server-rendered page with real links to three shell pages, and the three shell pages."""
    number = request.path.removeprefix('/holograms/mixed/')
    if number in _CHILDREN:
        return html(_shell(f'holograms-mixed-{number}'))
    if number:
        return None
    return html(article_page('holograms-mixed', [f'/holograms/mixed/{n}' for n in _CHILDREN]))


CASES: list[Case] = [
    section_case('holograms', 'Holograms: pages with no content without JavaScript',
                 ['/holograms/shell', '/holograms/short']),
    Case('holograms', 'shell', ('/holograms/shell',),
         'An empty container and a script that writes the article into it',
         lambda request: html(_shell('holograms-shell')), ('production only',)),
    Case('holograms', 'short-page', ('/holograms/short',), 'A server-rendered article of 150 words', _short,
         ('production only',)),
    Case('holograms', 'script-links', ('/holograms/script-links/', '/holograms/script-links/<n>'),
         'A server-rendered page of 250 words or more; a script adds the links to three articles', _script_links,
         ('own source', 'production only')),
    Case('holograms', 'mixed', ('/holograms/mixed/', '/holograms/mixed/<n>'),
         'A server-rendered source URL page with real links to three pages that are shells', _mixed,
         ('own source', 'production only')),
]
