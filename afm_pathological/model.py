from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Optional


@dataclass(frozen=True)
class Request:
    """One HTTP request to the site."""
    host: str  # the Host header as received: any letter case, can have a port
    path: str  # starts with '/', no query string
    method: str = 'GET'  # 'GET' or 'HEAD'
    query: str = ''  # raw query string without '?'
    headers: Mapping[str, str] = field(default_factory=dict)  # header names in lower case
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheme: str = 'https'

    @property
    def host_header(self) -> str:
        """The Host header in lower case; the x-pathological-host header replaces it."""
        return (self.headers.get('x-pathological-host') or self.host).lower()

    def url(self, path: str) -> str:
        """The absolute URL of a path on the host of this request."""
        return f'{self.scheme}://{self.host_header}{path}'

    def sibling_host(self, label: str) -> str:
        """The host of this request with its first label (after an optional www.) replaced; the port stays."""
        first, dot, rest = self.host_header.removeprefix('www.').partition('.')
        return f'{label}.{rest}' if dot else label + ''.join(first.partition(':')[1:])

    def sibling_url(self, label: str, path: str) -> str:
        """The absolute URL of a path on the sibling host of a label, such as librarian on the same domain."""
        return f'{self.scheme}://{self.sibling_host(label)}{path}'


@dataclass
class Response:
    """One HTTP response of the site."""
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)  # header names in lower case
    body: bytes = b''
    delay_sec: float = 0.0  # the server waits this long before it sends the first byte
    tear_after: Optional[int] = None  # the server closes the connection after this many body bytes
    validators: bool = True  # False: the site adds no ETag / Last-Modified and never answers 304
