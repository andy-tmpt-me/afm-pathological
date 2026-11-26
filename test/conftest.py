from datetime import datetime, timezone

import pytest

from afm_pathological.model import Request, Response
from afm_pathological.site import respond

NOW = datetime(2026, 11, 25, 12, 0, 45, tzinfo=timezone.utc)


@pytest.fixture
def fetch():
    """A function that sends one request to the site, by default to breadcrumbs at NOW."""

    def _fetch(path: str, host: str = 'breadcrumbs', method: str = 'GET', headers: dict[str, str] | None = None,
               now: datetime = NOW) -> Response:
        if '.' not in host and ':' not in host:
            host = f'{host}.pathological.answersfrom.me'
        return respond(Request(host=host, path=path, method=method, headers=headers or {}, now=now))

    return _fetch
