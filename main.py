import json
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

from afm_pathological import site
from afm_pathological.model import Request, Response

NOINDEX = 'noindex, nofollow'
_URL_SAFE = "!#$%&'()*+,/:;=?@[]~"  # quote keeps these and the unreserved characters, so escapes are not doubled


def header_value(name: str, value: str) -> str:
    """A value that send_header can write: non-ASCII in a location is percent-encoded as UTF-8, else replaced."""
    if value.isascii():
        return value
    return quote(value, safe=_URL_SAFE) if name == 'location' else value.encode('latin-1', 'replace').decode('latin-1')


class Handler(BaseHTTPRequestHandler):
    """Answers GET and HEAD requests with the response of the site."""
    protocol_version = 'HTTP/1.1'
    server_version = 'afm-pathological'

    def version_string(self) -> str:
        """The Server header of the answers of the standard library (405, 400): no Python version."""
        return self.server_version

    def send_response(self, code: int, message: str | None = None) -> None:
        """The status line of the answers that this module and the standard library build (405, 400), with noindex."""
        super().send_response(code, message)
        self.send_header('x-robots-tag', NOINDEX)

    def log_message(self, format, *args):
        """Silence the default access log; each request logs one JSON line instead."""

    def _log(self, severity: str, status: int, delay_sec: float = 0.0, error: str | None = None,
             stack: str | None = None) -> None:
        """Write one JSON log line to stdout."""
        entry = {'severity': severity, 'method': self.command, 'host': self.headers.get('Host', ''),
                 'path': self.path.split('?', 1)[0], 'status': status, 'delay_sec': delay_sec}
        if error:
            entry['error'] = error
        if stack:
            entry['stack'] = stack
        print(json.dumps(entry), flush=True)

    def _scheme(self) -> str:
        """The scheme of the first X-Forwarded-Proto value if it is http or https, else http."""
        proto = self.headers.get('x-forwarded-proto', '').split(',', 1)[0].strip().lower()
        return proto if proto in ('http', 'https') else 'http'

    def _request(self) -> Request:
        """Build the Request of the site from the HTTP request."""
        # http.server decodes the request line as Latin-1; a raw UTF-8 path must reach the site as UTF-8
        path, _, query = self.path.encode('latin-1').decode('utf-8', 'replace').partition('?')
        return Request(host=self.headers.get('Host', ''), path=path, method=self.command, query=query,
                       headers={name.lower(): value for name, value in self.headers.items()},
                       now=datetime.now(timezone.utc), scheme=self._scheme())

    def _send(self, response: Response) -> None:
        """Write the response: wait, headers, then the body unless HEAD or 304, torn off if the case says so."""
        if response.delay_sec:
            time.sleep(response.delay_sec)
        self.send_response_only(response.status)
        if 'date' not in response.headers:
            self.send_header('date', self.date_time_string())
        for name, value in {'content-length': str(len(response.body)), **response.headers}.items():
            if name == 'content-length' and response.status == 304:  # RFC 9110: only the length of the 200 is allowed
                continue
            self.send_header(name, header_value(name, value))
        self.end_headers()
        if self.command == 'HEAD' or response.status == 304:
            return
        if response.tear_after is None:
            self.wfile.write(response.body)
        else:
            self.wfile.write(response.body[:response.tear_after])
            self.close_connection = True

    def _serve(self) -> None:
        """Answer one GET or HEAD request; the log line is written before the response is sent."""
        try:
            response = site.respond(self._request())
            self._log('INFO', response.status, response.delay_sec)
        except Exception as e:  # pylint: disable=broad-except
            response = Response(500, {'content-type': 'text/plain', 'x-robots-tag': NOINDEX}, b'Internal Server Error')
            self._log('ERROR', 500, error=f'{type(e).__name__}: {e}', stack=traceback.format_exc())
        try:
            self._send(response)
        except OSError as e:  # the client went away, as bots do on slow and torn responses
            self.close_connection = True
            self._log('WARNING', response.status, response.delay_sec, error=f'client disconnected: {e}')

    do_GET = do_HEAD = _serve

    def _method_not_allowed(self) -> None:
        """Answer any other method with 405 and close the connection, since the request body is not read."""
        self._log('INFO', 405)
        self.send_response(405)
        self.send_header('allow', 'GET, HEAD')
        self.send_header('content-length', '0')
        self.send_header('connection', 'close')
        self.end_headers()

    def __getattr__(self, name: str):
        """Route the do_<METHOD> of every other method to the 405 answer."""
        if name.startswith('do_'):
            return self._method_not_allowed
        raise AttributeError(name)


class Server(ThreadingHTTPServer):
    """The HTTP server, with a listen backlog for bursts of bots and one JSON line for an exception of a connection."""
    request_queue_size = 128

    def handle_error(self, request, client_address) -> None:
        """A failed connection (OSError, such as a client reset) is one WARNING line; any other error is ERROR."""
        error = sys.exc_info()[1]
        entry = {'severity': 'WARNING', 'client': client_address[0],
                 'error': f'connection failed: {type(error).__name__}: {error}'}
        if not isinstance(error, OSError):
            entry.update(severity='ERROR', stack=traceback.format_exc())
        print(json.dumps(entry), flush=True)


def make_server(port: int) -> Server:
    """A server on all interfaces; port 0 picks a free port."""
    server = Server(('0.0.0.0', port), Handler)
    server.daemon_threads = True
    return server


def main() -> None:
    """Serve until SIGTERM."""
    server = make_server(int(os.environ.get('PORT', '8080')))
    # shutdown() blocks until serve_forever returns, so it cannot run in the signal handler of the serving thread
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown).start())
    server.serve_forever()
    server.server_close()


if __name__ == '__main__':
    main()
