import re
from datetime import date, datetime, time, timezone
from email.utils import format_datetime
from typing import Optional

from afm_pathological.model import Request

EPOCH = date(2026, 1, 1)
LAST_DATE = date(9000, 1, 1)  # a later header date is ignored, so that date arithmetic forward cannot overflow
_ISO_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')


def parse_date(value: str) -> Optional[date]:
    """The date of a YYYY-MM-DD string, or None."""
    if not _ISO_DATE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def today(request: Request) -> date:
    """The date in effect: a valid X-Pathological-Date from EPOCH to LAST_DATE, else the UTC date of the request."""
    day = parse_date(request.headers.get('x-pathological-date', ''))
    return day if day and EPOCH <= day <= LAST_DATE else request.now.astimezone(timezone.utc).date()


def day_number(request: Request) -> int:
    """The number of days from 2026-01-01 to the date in effect."""
    return (today(request) - EPOCH).days


def in_error_slot(request: Request) -> bool:
    """True in seconds 0 to 29 of the minute."""
    return request.now.second < 30


def http_date(value: datetime | date) -> str:
    """An RFC 7231 date in GMT."""
    if not isinstance(value, datetime):
        value = datetime.combine(value, time(), timezone.utc)
    return format_datetime(value.astimezone(timezone.utc), usegmt=True)
