from html import escape
from typing import Sequence

from afm_pathological.content import Article, article


# Without it a phone lays the page out at desktop width and shrinks the text
_VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'


def page(title: str, body_html: str, head_html: str = '') -> str:
    """A complete HTML document with the title as <title> and <h1>."""
    head = (f'<meta charset="utf-8">\n{_VIEWPORT}\n<title>{escape(title)}</title>\n{head_html}').rstrip('\n')
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n{head}\n</head>\n'
            f'<body>\n<h1>{escape(title)}</h1>\n{body_html}\n</body>\n</html>\n')


def links_html(links: Sequence[str | tuple[str, str]]) -> str:
    """A <ul> of <a href> elements; a bare path is its own anchor text."""
    if not links:
        return ''
    items = []
    for link in links:
        href, text = (link, link) if isinstance(link, str) else link
        items.append(f'<li><a href="{escape(href)}">{escape(text)}</a></li>')
    return '<ul>\n' + '\n'.join(items) + '\n</ul>'


def article_body(a: Article, links: Sequence[str | tuple[str, str]] = ()) -> str:
    """The paragraphs of an article in <p> elements, followed by the links."""
    return '\n'.join([f'<p>{escape(p)}</p>' for p in a.paragraphs] + [links_html(links)]).rstrip('\n')


def article_page(key: str, links: Sequence[str | tuple[str, str]] = (), variant: int = 0, head_html: str = '') -> str:
    """A complete HTML page of the article of a key, with the links after the text."""
    a = article(key, variant)
    return page(a.title, article_body(a, links), head_html)
