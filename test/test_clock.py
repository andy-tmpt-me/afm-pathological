from datetime import date, datetime, timedelta, timezone

from afm_pathological.clock import EPOCH, day_number, http_date, in_error_slot, today
from afm_pathological.model import Request


def _request(now: datetime, headers: dict[str, str] | None = None) -> Request:
    """A request at the given time."""
    return Request(host='breadcrumbs.localhost', path='/', headers=headers or {}, now=now)


def test_day_number_counts_from_epoch():
    """Day 0 is 2026-01-01 and the count follows the UTC date."""
    assert EPOCH == date(2026, 1, 1)
    assert day_number(_request(datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc))) == 0
    assert day_number(_request(datetime(2026, 11, 25, 23, 59, tzinfo=timezone.utc))) == 328


def test_today_uses_utc_date():
    """A time in a different zone is converted to the UTC date."""
    plus_two = timezone(timedelta(hours=2))
    assert today(_request(datetime(2026, 3, 2, 1, 0, tzinfo=plus_two))) == date(2026, 3, 1)


def test_date_header_replaces_date():
    """X-Pathological-Date replaces the date when it is a valid ISO date."""
    now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    assert today(_request(now, {'x-pathological-date': '2026-03-01'})) == date(2026, 3, 1)
    assert day_number(_request(now, {'x-pathological-date': '2026-01-11'})) == 10
    assert today(_request(now, {'x-pathological-date': 'tomorrow'})) == date(2026, 11, 25)
    assert today(_request(now, {'x-pathological-date': '20260301'})) == date(2026, 11, 25)


def test_error_slot_is_first_half_minute():
    """Seconds 0 to 29 are the error slot, 30 to 59 the ok slot."""
    base = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    assert in_error_slot(_request(base))
    assert in_error_slot(_request(base.replace(second=29)))
    assert not in_error_slot(_request(base.replace(second=30)))
    assert not in_error_slot(_request(base.replace(second=59)))


def test_http_date():
    """Dates and datetimes format as RFC 7231 GMT dates."""
    assert http_date(date(2026, 1, 1)) == 'Thu, 01 Jan 2026 00:00:00 GMT'
    assert http_date(datetime(2026, 11, 25, 12, 30, 5, tzinfo=timezone.utc)) == 'Wed, 25 Nov 2026 12:30:05 GMT'
