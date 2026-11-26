import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

import pytest

from afm_pathological.content import article
from afm_pathological.feedgen import Entry, atom, rss

ATOM = '{http://www.w3.org/2005/Atom}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'
BASE = 'https://town-crier.pathological.answersfrom.me'
RSS_TYPE = 'application/rss+xml'
FEEDS = ('atom', 'backdated', 'edited', 'undated', 'long', 'long-oldest-first', 'full-text', 'odd')


def _feed(fetch, path: str, **kwargs):
    """The parsed XML root of a feed of town-crier."""
    response = fetch(path, host='town-crier', **kwargs)
    assert response.status == 200
    return ET.fromstring(response.body)


def _items(root) -> list[ET.Element]:
    """The <item> elements of an RSS feed."""
    return root.findall('channel/item')


def _link_dates(root) -> list[str]:
    """The date part of the /daily/<date> link of each entry of an RSS feed."""
    return [item.findtext('link').rsplit('/', 1)[1] for item in _items(root)]


def test_rss_and_atom_writers():
    """rss and atom write escaped text, the content namespace only for full text, and skip absent parts."""
    when = datetime(2026, 3, 1, 6, tzinfo=timezone.utc)
    entries = [Entry('A & B', 'https://x/a', when, 'short', '<p>full</p>', 'g1'), Entry(guid='g2', description='d')]
    root = ET.fromstring(rss('T', 'https://x/', entries, when))
    assert root.findtext('channel/lastBuildDate') == 'Sun, 01 Mar 2026 06:00:00 GMT'
    first, second = _items(root)
    assert first.findtext('title') == 'A & B'
    assert first.findtext('pubDate') == 'Sun, 01 Mar 2026 06:00:00 GMT'
    assert first.findtext(f'{CONTENT}encoded') == '<p>full</p>'
    assert [child.tag for child in second] == ['guid', 'description']
    assert 'xmlns:content' not in rss('T', 'https://x/', [entries[1]], None)
    assert ET.fromstring(rss('T', 'https://x/', entries[:1], None)).find('channel/lastBuildDate') is None
    feed = ET.fromstring(atom('T', 'https://x/', entries, when))
    assert feed.findtext(f'{ATOM}updated') == '2026-03-01T06:00:00Z'
    assert [e.findtext(f'{ATOM}id') for e in feed.findall(f'{ATOM}entry')] == ['g1', 'g2']
    assert ET.fromstring(atom('T', 'https://x/', entries, None)).find(f'{ATOM}updated') is None


def test_daily_feed_on_town_crier(fetch):
    """/feed has the last 10 daily pages, newest first, dated 06:00 UTC, with the page title and first paragraph."""
    response = fetch('/feed', host='town-crier')
    assert response.headers['content-type'].startswith(RSS_TYPE)
    root = ET.fromstring(response.body)
    items = _items(root)
    assert _link_dates(root) == [str(date(2026, 11, 25) - timedelta(days=i)) for i in range(10)]
    assert items[0].findtext('link') == f'{BASE}/daily/2026-11-25'
    assert items[0].findtext('title') == article('daily-2026-11-25').title
    assert items[0].findtext('description') == article('daily-2026-11-25').paragraphs[0]
    assert items[0].findtext('pubDate') == 'Wed, 25 Nov 2026 06:00:00 GMT'
    assert root.findtext('channel/lastBuildDate') == 'Wed, 25 Nov 2026 06:00:00 GMT'


def test_daily_feed_gets_one_new_entry_a_day(fetch):
    """One day later the oldest entry has left and one new entry is first."""
    today = _link_dates(_feed(fetch, '/feed'))
    tomorrow = _link_dates(_feed(fetch, '/feed', headers={'x-pathological-date': '2026-11-26'}))
    assert tomorrow[0] == '2026-11-26' and tomorrow[1:] == today[:-1]


def test_atom_feed(fetch):
    """/feeds/atom.xml is the daily feed as Atom, with <updated> of the newest entry."""
    response = fetch('/feeds/atom.xml', host='town-crier')
    assert response.headers['content-type'].startswith('application/atom+xml')
    root = ET.fromstring(response.body)
    entries = root.findall(f'{ATOM}entry')
    assert len(entries) == 10
    assert root.findtext(f'{ATOM}updated') == '2026-11-25T06:00:00Z'
    assert entries[0].find(f'{ATOM}link').get('href') == f'{BASE}/daily/2026-11-25'
    assert entries[0].findtext(f'{ATOM}updated') == '2026-11-25T06:00:00Z'


def test_every_feed_is_on_every_host(fetch):
    """Each feed case parses on a host other than town-crier, with an RSS or Atom content type."""
    for name in FEEDS:
        response = fetch(f'/feeds/{name}.xml', host='breadcrumbs')
        assert response.status == 200, name
        assert response.headers['content-type'].startswith(('application/rss+xml', 'application/atom+xml')), name
        ET.fromstring(response.body)


def test_backdated_feed(fetch):
    """backdated.xml has the daily entries, each dated 2026-01-01 06:00 UTC, and no feed-level date."""
    for day in ('2026-11-25', '2026-11-26'):
        headers = {'x-pathological-date': day}
        root = _feed(fetch, '/feeds/backdated.xml', headers=headers)
        assert _link_dates(root) == _link_dates(_feed(fetch, '/feed', headers=headers))
        assert {item.findtext('pubDate') for item in _items(root)} == {'Thu, 01 Jan 2026 06:00:00 GMT'}
        assert root.find('channel/lastBuildDate') is None and root.find('channel/pubDate') is None


def test_edited_feed(fetch):
    """edited.xml is the daily feed plus the honest-edit page last, dated 06:00 UTC of the request date."""
    for day in ('2026-11-25', '2026-11-26'):
        items = _items(_feed(fetch, '/feeds/edited.xml', headers={'x-pathological-date': day}))
        assert len(items) == 11
        assert items[-1].findtext('link') == f'{BASE}/chameleons/honest-edit'
        assert items[-1].findtext('pubDate') == f'{datetime.fromisoformat(day):%a, %d %b %Y} 06:00:00 GMT'


def test_undated_feed(fetch):
    """undated.xml has the daily entries with no date and no feed-level date."""
    root = _feed(fetch, '/feeds/undated.xml')
    assert len(_items(root)) == 10
    assert not root.findall('channel/item/pubDate')
    assert root.find('channel/lastBuildDate') is None and root.find('channel/pubDate') is None


def test_long_feeds(fetch):
    """long.xml has 600 entries, newest first; long-oldest-first.xml has the reverse order."""
    newest_first = _link_dates(_feed(fetch, '/feeds/long.xml'))
    assert len(newest_first) == 600
    assert newest_first[0] == '2026-11-25' and newest_first[1] == '2026-11-24'
    assert newest_first[-1] == str(date(2026, 11, 25) - timedelta(days=599))
    assert _link_dates(_feed(fetch, '/feeds/long-oldest-first.xml')) == newest_first[::-1]


def test_full_text_feed(fetch):
    """full-text.xml has the article as HTML in content:encoded, and one description of 2,500 characters."""
    items = _items(_feed(fetch, '/feeds/full-text.xml'))
    assert len(items) == 10
    paragraphs = article('daily-2026-11-25').paragraphs
    assert all(p in items[0].findtext(f'{CONTENT}encoded') for p in paragraphs)
    assert items[0].findtext(f'{CONTENT}encoded').startswith('<p>')
    lengths = [len(item.findtext('description')) for item in items]
    assert lengths.count(2500) == 1 and max(lengths[1:]) < 500


def test_odd_feed(fetch):
    """odd.xml has a guid-only entry, two entries with one link, a relative link and an entry with no title."""
    items = _items(_feed(fetch, '/feeds/odd.xml'))
    guid_only = [i for i in items if i.find('link') is None]
    assert len(guid_only) == 1 and guid_only[0].findtext('guid') and guid_only[0].find('title') is None
    links = [i.findtext('link') for i in items if i.find('link') is not None]
    assert len(links) - len(set(links)) == 1
    assert any(link.startswith('/') for link in links)
    assert [i.find('title') is None for i in items].count(True) == 2


def test_outage_feed(fetch):
    """outage.xml is the daily feed on an even day number and 503 on an odd one."""
    even = fetch('/feeds/outage.xml', headers={'x-pathological-date': '2026-01-03'})
    odd = fetch('/feeds/outage.xml', headers={'x-pathological-date': '2026-01-02'})
    assert (even.status, odd.status) == (200, 503)
    assert len(_items(ET.fromstring(even.body))) == 3


def test_feeds_in_readme(fetch):
    """The README lists the feed paths."""
    markdown = fetch('/README.md').body.decode()
    for name in FEEDS + ('outage',):
        assert f'`/feeds/{name}.xml`' in markdown


def test_long_feeds_link_to_long_pages(fetch):
    """Each of the 600 entries of both long feeds links to a /feeds/long/<date> page that answers 200."""
    for name in ('long', 'long-oldest-first'):
        links = [item.findtext('link') for item in _items(_feed(fetch, f'/feeds/{name}.xml'))]
        assert len(links) == 600 and all(link.startswith(f'{BASE}/feeds/long/') for link in links)
        assert {fetch(link.removeprefix(BASE), host='town-crier').status for link in links} == {200}


def test_long_page_dates(fetch):
    """A long page exists from 800 days before the date in effect up to that date, and is 404 otherwise."""
    day = date(2026, 11, 25)
    for offset, status in ((0, 200), (800, 200), (801, 404), (-1, 404)):
        assert fetch(f'/feeds/long/{day - timedelta(days=offset)}', host='town-crier').status == status, offset
    assert fetch('/feeds/long/not-a-date', host='town-crier').status == 404
    page = fetch(f'/feeds/long/{day}', host='town-crier').body.decode()
    entry = _items(_feed(fetch, '/feeds/long.xml'))[0]
    assert f'<title>{entry.findtext("title")}</title>' in page


def test_atom_with_no_entries_before_epoch(fetch):
    """Atom on 2026-01-01 has one entry; it never fails on a date with fewer entries."""
    root = _feed(fetch, '/feeds/atom.xml', headers={'x-pathological-date': '2026-01-01'})
    assert len(root.findall(f'{ATOM}entry')) == 1


@pytest.mark.parametrize('name', ['undated', 'backdated'])
def test_feeds_with_no_date_send_no_validators(fetch, name):
    """undated.xml and backdated.xml send no ETag and no Last-Modified, and never answer 304."""
    response = fetch(f'/feeds/{name}.xml', host='town-crier')
    assert 'etag' not in response.headers and 'last-modified' not in response.headers
    later = {'if-modified-since': 'Fri, 01 Jan 2100 00:00:00 GMT'}
    assert fetch(f'/feeds/{name}.xml', host='town-crier', headers=later).status == 200


def test_dated_feeds_keep_last_modified(fetch):
    """The other feeds keep the request date as Last-Modified."""
    for path in ('/feed', '/feeds/atom.xml', '/feeds/long.xml', '/feeds/edited.xml'):
        assert fetch(path, host='town-crier').headers['last-modified'] == 'Wed, 25 Nov 2026 00:00:00 GMT', path


def test_atom_link_attributes_are_escaped(fetch):
    """A host with a quote and an ampersand still gives Atom that parses, with the host in each href."""
    response = fetch('/feeds/atom.xml', host='town-crier.a"b&c')
    root = ET.fromstring(response.body)
    assert root.find(f'{ATOM}link').get('href') == 'https://town-crier.a"b&c/'
    assert root.find(f'{ATOM}entry/{ATOM}link').get('href').startswith('https://town-crier.a"b&c/daily/')
