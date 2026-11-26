from difflib import SequenceMatcher
from itertools import combinations

from afm_pathological.content import article
from afm_pathological.pages import article_page, links_html, page

KEYS = ['starter', 'hydration', 'scoring', 'steam', 'crumb', 'unlisted', 'flour', 'salt', 'articles', 'notes',
        'daily', 'daily-2026-11-25', 'daily-2026-11-24', 'chameleons', 'tangle']


def test_article_is_long_and_on_topic():
    """Each article has 4 or more paragraphs, 250 or more words and mentions sourdough."""
    for key in KEYS:
        a = article(key)
        assert len(a.paragraphs) >= 4
        assert sum(len(p.split()) for p in a.paragraphs) >= 250
        assert 'sourdough' in ' '.join(a.paragraphs).lower()


def test_article_is_deterministic():
    """The same key and variant give the same article."""
    assert article('starter', 3) == article('starter', 3)


def test_titles_unique_and_long():
    """Each key has its own title of more than 10 characters."""
    titles = [article(key).title for key in KEYS]
    assert len(set(titles)) == len(KEYS)
    assert all(len(t) > 10 for t in titles)


def test_keys_differ_in_more_than_20_percent():
    """The texts of two keys differ in more than 20% of their characters."""
    for a, b in combinations(KEYS, 2):
        ratio = SequenceMatcher(None, ' '.join(article(a).paragraphs), ' '.join(article(b).paragraphs)).ratio()
        assert ratio < 0.8, (a, b, ratio)


def test_variant_changes_exactly_one_paragraph():
    """A different variant changes one paragraph and keeps the title."""
    for key in KEYS:
        for v1, v2 in [(0, 1), (1, 2), (0, 40), (5, 365), (0, 1600)]:
            a, b = article(key, v1), article(key, v2)
            assert a.title == b.title
            assert sum(p != q for p, q in zip(a.paragraphs, b.paragraphs)) == 1, (key, v1, v2)


def test_page_structure():
    """A page is a complete HTML document with the title as <title> and <h1>, and no script or style."""
    html = page('Sourdough & friends', '<p>Body</p>', head_html='<meta name="x" content="y">')
    assert html.startswith('<!DOCTYPE html>')
    assert '<html lang="en">' in html
    assert '<meta charset="utf-8">' in html
    assert '<title>Sourdough &amp; friends</title>' in html
    assert '<meta name="x" content="y">' in html.split('</head>')[0]
    assert '<h1>Sourdough &amp; friends</h1>' in html.split('<body>')[1]
    assert '<p>Body</p>' in html
    for marker in ('<script', 'stylesheet', '<nav'):
        assert marker not in html


def test_links_html():
    """Links render as a list of anchors with text; a bare path is its own anchor text."""
    html = links_html(['/a', ('/b?x=1&y=2', 'Bee')])
    assert html.startswith('<ul>')
    assert '<a href="/a">/a</a>' in html
    assert '<a href="/b?x=1&amp;y=2">Bee</a>' in html
    assert links_html([]) == ''


def test_article_page_has_paragraphs_then_links():
    """An article page has the paragraphs of the article in <p> elements and then its links."""
    html = article_page('starter', ['/articles/unlisted'])
    a = article('starter')
    assert f'<title>{a.title}</title>' in html
    assert html.count('<p>') == len(a.paragraphs)
    assert html.index('</p>') < html.index('<a href="/articles/unlisted">')
    assert '<a ' not in article_page('starter')
