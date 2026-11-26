from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Optional, Sequence
from xml.sax.saxutils import escape, quoteattr

_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n'
_CONTENT_NS = 'http://purl.org/rss/1.0/modules/content/'


@dataclass(frozen=True)
class Entry:
    """One feed entry; each part that is empty or None is left out of the feed."""
    title: str = ''
    link: Optional[str] = None
    date: Optional[datetime] = None
    description: str = ''
    full_html: Optional[str] = None  # the whole article, for content:encoded
    guid: Optional[str] = None


def _tag(name: str, value: Optional[str], attrs: str = '') -> str:
    """An element with escaped text, or nothing when the value is None or empty."""
    return f'<{name}{attrs}>{escape(value)}</{name}>\n' if value else ''


def _iso(value: datetime) -> str:
    """A UTC date and time for Atom."""
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _rfc(value: datetime) -> str:
    """A UTC date and time for RSS."""
    return format_datetime(value.astimezone(timezone.utc), usegmt=True)


def rss(title: str, link: str, entries: Sequence[Entry], last_build: Optional[datetime]) -> str:
    """An RSS 2.0 feed; it declares the content namespace when an entry has full text."""
    namespace = f' xmlns:content="{_CONTENT_NS}"' if any(e.full_html for e in entries) else ''
    items = ''.join(
        '<item>\n' + _tag('title', e.title) + _tag('link', e.link) + _tag('guid', e.guid, ' isPermaLink="false"')
        + (_tag('pubDate', _rfc(e.date)) if e.date else '')
        + f'<description>{escape(e.description)}</description>\n' + _tag('content:encoded', e.full_html)
        + '</item>\n' for e in entries)
    build = _tag('lastBuildDate', _rfc(last_build)) if last_build else ''
    return (f'{_HEAD}<rss version="2.0"{namespace}>\n<channel>\n{_tag("title", title)}{_tag("link", link)}'
            f'<description>{escape(title)}</description>\n{build}{items}</channel>\n</rss>\n')


def atom(title: str, link: str, entries: Sequence[Entry], updated: Optional[datetime]) -> str:
    """An Atom feed."""
    items = ''.join(
        '<entry>\n' + _tag('title', e.title) + (f'<link href={quoteattr(e.link)}/>\n' if e.link else '')
        + _tag('id', e.guid or e.link or e.title) + (_tag('updated', _iso(e.date)) if e.date else '')
        + _tag('summary', e.description) + _tag('content', e.full_html, ' type="html"') + '</entry>\n'
        for e in entries)
    return (f'{_HEAD}<feed xmlns="http://www.w3.org/2005/Atom">\n{_tag("title", title)}<link href={quoteattr(link)}/>\n'
            f'{_tag("id", link)}{_tag("updated", _iso(updated)) if updated else ""}{items}</feed>\n')
