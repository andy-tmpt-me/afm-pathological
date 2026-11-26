from afm_pathological.model import Response


def html(body: str, status: int = 200, headers: dict[str, str] | None = None) -> Response:
    """An HTML response."""
    return Response(status, {'content-type': 'text/html; charset=utf-8', **(headers or {})}, body.encode())


def text(body: str, status: int = 200, content_type: str = 'text/plain; charset=utf-8') -> Response:
    """A text response of any content type."""
    return Response(status, {'content-type': content_type}, body.encode())


def xml(body: str, content_type: str = 'application/xml') -> Response:
    """An XML response."""
    return text(body, content_type=content_type)


def redirect(location: str, status: int = 301) -> Response:
    """A redirect to a location."""
    return Response(status, {'location': location})


def not_found() -> Response:
    """A 404 with a short HTML body and no validators."""
    response = html('<!DOCTYPE html>\n<html lang="en"><head><title>Not found</title></head>'
                    '<body><p>Not found.</p></body></html>\n', status=404)
    response.validators = False
    return response
