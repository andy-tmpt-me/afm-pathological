import http.client
import json
import re
import socket
import struct
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import pytest

import main
from afm_pathological import site
from afm_pathological.model import Request, Response

HOST = {'Host': 'breadcrumbs.localhost'}


@pytest.fixture
def server():
    """A running server on a free port; yields the port."""
    httpd = main.make_server(0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def _request(port: int, method: str = 'GET', path: str = '/', headers: dict[str, str] | None = None,
             body: bytes | None = None):
    """Send one request and return (response, body); the body read can raise IncompleteRead."""
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers or HOST)
        response = conn.getresponse()
        return response, response.read()
    finally:
        conn.close()


def test_get_regular_page_matches_respond(server):
    response, body = _request(server, path='/articles/')
    expected = site.respond(Request(host='breadcrumbs.localhost', path='/articles/', scheme='http'))
    assert response.status == 200
    assert body == expected.body


def test_head_has_no_body_and_get_content_length(server):
    get, body = _request(server, path='/articles/')
    head, head_body = _request(server, 'HEAD', '/articles/')
    assert head_body == b''
    assert head.getheader('content-length') == get.getheader('content-length') == str(len(body))


def test_post_gives_405(server):
    response, _ = _request(server, 'POST', '/articles/')
    assert response.status == 405
    assert response.getheader('allow') == 'GET, HEAD'


def test_post_with_body_closes_the_connection(server):
    smuggled = b'GET /articles/ HTTP/1.1\r\nHost: breadcrumbs.localhost\r\n\r\n'
    conn = http.client.HTTPConnection('127.0.0.1', server, timeout=5)
    conn.request('POST', '/articles/', body=smuggled, headers=HOST)
    response = conn.getresponse()
    response.read()
    assert response.status == 405 and response.will_close
    assert conn.sock is None or conn.sock.recv(1) == b''  # the server closed it; the body was not parsed as a request
    conn.close()
    assert _request(server, path='/articles/')[0].status == 200


def test_unusual_method_gives_405(server):
    response, _ = _request(server, 'PROPFIND', '/articles/')
    assert response.status == 405
    assert response.getheader('allow') == 'GET, HEAD'


def test_not_modified_has_no_body(server):
    first, _ = _request(server, path='/articles/')
    response, body = _request(server, path='/articles/', headers={**HOST, 'If-None-Match': first.getheader('etag')})
    assert (response.status, body) == (304, b'')


def test_not_modified_has_no_content_length_and_keeps_the_connection(server):
    """A 304 sends no Content-Length and no body, and the next request on the same connection works."""
    first, _ = _request(server, path='/articles/')
    conn = http.client.HTTPConnection('127.0.0.1', server, timeout=5)
    conn.request('GET', '/articles/', headers={**HOST, 'If-None-Match': first.getheader('etag')})
    response = conn.getresponse()
    assert (response.status, response.getheader('content-length'), response.read()) == (304, None, b'')
    conn.request('GET', '/articles/', headers=HOST)
    again = conn.getresponse()
    assert again.status == 200 and again.read() == site.respond(
        Request(host='breadcrumbs.localhost', path='/articles/', scheme='http')).body
    conn.close()


def test_tear_after_gives_incomplete_read(server, monkeypatch):
    monkeypatch.setattr(site, 'respond', lambda request: Response(body=b'x' * 1000, tear_after=100))
    with pytest.raises(http.client.IncompleteRead) as error:
        _request(server)
    assert error.value.partial == b'x' * 100


def test_delay_sec_waits_before_answering(server, monkeypatch):
    monkeypatch.setattr(site, 'respond', lambda request: Response(body=b'late', delay_sec=0.2))
    conn = http.client.HTTPConnection('127.0.0.1', server, timeout=5)
    start = time.monotonic()
    conn.request('GET', '/', headers=HOST)
    response = conn.getresponse()
    assert time.monotonic() - start >= 0.2
    assert response.read() == b'late'
    conn.close()


def test_handler_exception_gives_500_and_error_log(server, monkeypatch, capsys):
    def boom(request):
        raise ValueError('kaput')

    monkeypatch.setattr(site, 'respond', boom)
    response, _ = _request(server)
    assert response.status == 500
    entry = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert entry['severity'] == 'ERROR' and 'kaput' in entry['error'] and entry['status'] == 500


def test_log_line_is_json(server, capsys):
    _request(server, path='/articles/')
    entry = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert entry == {'severity': 'INFO', 'method': 'GET', 'host': 'breadcrumbs.localhost', 'path': '/articles/',
                     'status': 200, 'delay_sec': 0.0}


def test_client_disconnect_logs_warning_not_error(server, monkeypatch, capsys):
    def broken(self, response):
        raise BrokenPipeError('gone')

    monkeypatch.setattr(main.Handler, '_send', broken)
    with pytest.raises(http.client.RemoteDisconnected):
        _request(server, path='/articles/')
    time.sleep(0.2)  # the server logs after the failed send, with no response to wait for
    entries = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [entry['severity'] for entry in entries] == ['INFO', 'WARNING']
    assert 'gone' in entries[-1]['error']


def _raw(port: int, data: bytes) -> bytes:
    """Send raw bytes and return all bytes of the answer until the server closes the connection."""
    with socket.create_connection(('127.0.0.1', port), timeout=5) as sock:
        sock.sendall(data)
        chunks = []
        while chunk := sock.recv(65536):
            chunks.append(chunk)
    return b''.join(chunks)


def test_listen_backlog():
    """The server accepts a burst of connections: its listen backlog is 128, not the default 5."""
    httpd = main.make_server(0)
    try:
        assert httpd.request_queue_size == 128
    finally:
        httpd.server_close()


def test_cdn_headers_has_one_date(server):
    """cdn-headers has exactly one Date header, the one of the site, and Age 600."""
    response, _ = _request(server, path='/chameleons/cdn-headers')
    dates = response.msg.get_all('Date')
    assert len(dates) == 1 and response.getheader('age') == '600'
    assert abs((parsedate_to_datetime(dates[0]) - datetime.now(timezone.utc)).total_seconds()) < 5


def test_site_date_header_is_sent_as_is(server, monkeypatch):
    """A date header of the site replaces the date of the server."""
    monkeypatch.setattr(site, 'respond', lambda request: Response(headers={'date': 'Thu, 01 Jan 2026 00:00:00 GMT'}))
    response, _ = _request(server)
    assert response.msg.get_all('Date') == ['Thu, 01 Jan 2026 00:00:00 GMT']


def test_server_adds_one_date_and_no_version(server):
    """A page with no date of its own gets one Date; no answer names the Python version, also 405 and 400."""
    response, _ = _request(server, path='/articles/')
    assert len(response.msg.get_all('Date')) == 1
    assert 'Python' not in (response.getheader('server') or '')
    response, _ = _request(server, 'POST', '/articles/')
    assert len(response.msg.get_all('Date')) == 1 and 'Python' not in (response.getheader('server') or '')
    bad = _raw(server, b'NONSENSE\r\n\r\n')
    assert bad.startswith(b'HTTP/1.1 400') or bad.startswith(b'HTTP/1.0 400')
    assert b'Python' not in bad and b'BaseHTTP' not in bad


def test_client_reset_logs_one_warning_line(server, capsys):
    """A client that resets the connection while the request line is read gives one JSON WARNING line, no traceback."""
    sock = socket.create_connection(('127.0.0.1', server), timeout=5)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
    sock.sendall(b'GET /articles/ HTT')
    time.sleep(0.1)
    sock.close()  # linger 0 sends a reset
    time.sleep(0.3)
    captured = capsys.readouterr()
    assert 'Traceback' not in captured.err
    entries = [json.loads(line) for line in captured.out.strip().splitlines()]
    assert [entry['severity'] for entry in entries] == ['WARNING'] and 'Reset' in entries[0]['error']


def test_error_log_has_a_stack(server, monkeypatch, capsys):
    """The ERROR line of a 500 has the stack trace."""
    def boom(request):
        raise ValueError('kaput')

    monkeypatch.setattr(site, 'respond', boom)
    _request(server)
    entry = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert 'Traceback' in entry['stack'] and 'kaput' in entry['stack']


def test_raw_utf8_path_is_decoded(server):
    """A raw UTF-8 path reaches the site as UTF-8: /tangle/café answers its page."""
    answer = _raw(server, 'GET /tangle/café HTTP/1.1\r\nHost: breadcrumbs.localhost\r\nConnection: close\r\n\r\n'
                  .encode())
    assert answer.startswith(b'HTTP/1.1 200')
    latin1 = _raw(server, b'GET /tangle/caf\xe9 HTTP/1.1\r\nHost: breadcrumbs.localhost\r\nConnection: close\r\n\r\n')
    assert latin1.startswith(b'HTTP/1.1 404')


@pytest.mark.parametrize('proto, scheme', [
    (None, 'http'), ('https', 'https'), ('http', 'http'), ('https, http', 'https'), ('javascript', 'http'),
    ('https"x', 'http'), ('', 'http')])
def test_forwarded_proto(server, proto, scheme):
    """Only http or https from the first value of X-Forwarded-Proto goes into generated URLs."""
    headers = {'Host': 'mirage.localhost', **({'X-Forwarded-Proto': proto} if proto is not None else {})}
    _, body = _request(server, path='/robots.txt', headers=headers)
    assert body.decode().splitlines()[-1] == f'Sitemap: {scheme}://mirage.localhost/sitemap.xml'


def _location(answer: bytes) -> bytes:
    """The value of the Location header of a raw answer."""
    return re.search(rb'(?im)^location: (.*?)\r$', answer).group(1)


@pytest.mark.parametrize('target, location', [
    ('/€'.encode(), b'http://librarian.localhost/%E2%82%AC'),
    (b'/caf\xe9', b'http://librarian.localhost/caf%EF%BF%BD'),
    ('/x?q=€'.encode(), b'http://librarian.localhost/x?q=%E2%82%AC'),
    ('/café'.encode(), b'http://librarian.localhost/caf%C3%A9'),
    (b'/caf%C3%A9', b'http://librarian.localhost/caf%C3%A9')])
def test_non_ascii_location_is_percent_encoded(server, target, location):
    """A redirect to a path with non-ASCII characters answers 301 with a pure ASCII, percent-encoded Location."""
    answer = _raw(server, b'GET ' + target + b' HTTP/1.1\r\nHost: forwarding-address.localhost\r\n'
                  b'Connection: close\r\n\r\n')
    assert answer.startswith(b'HTTP/1.1 301') and _location(answer) == location


def test_non_latin1_header_value_is_replaced(server, monkeypatch):
    """A header value outside Latin-1 is sent with replacement characters instead of failing the answer."""
    monkeypatch.setattr(site, 'respond', lambda request: Response(headers={'x-note': 'price €5'}, body=b'ok'))
    response, body = _request(server)
    assert (response.status, body, response.getheader('x-note')) == (200, b'ok', 'price ?5')


def test_bug_outside_serve_logs_error_with_stack(server, monkeypatch, capsys):
    """An exception that is not an OSError and escapes the handler is one ERROR line with the stack."""
    def broken(self, response):
        raise ValueError('kaput')

    monkeypatch.setattr(main.Handler, '_send', broken)
    with pytest.raises(http.client.RemoteDisconnected):
        _request(server, path='/articles/')
    time.sleep(0.2)
    entry = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert entry['severity'] == 'ERROR' and 'kaput' in entry['error'] and 'Traceback' in entry['stack']


def test_server_built_answers_say_noindex(server, monkeypatch):
    """The 405, the 500 and the standard library's 400 answer also have x-robots-tag."""
    assert _request(server, 'POST', '/articles/')[0].getheader('x-robots-tag') == 'noindex, nofollow'
    assert b'x-robots-tag: noindex, nofollow' in _raw(server, b'NONSENSE\r\n\r\n').lower()
    monkeypatch.setattr(site, 'respond', lambda request: 1 / 0)
    assert _request(server)[0].getheader('x-robots-tag') == 'noindex, nofollow'
