from unittest.mock import Mock

from webspark.core.router import path
from webspark.core.views import View
from webspark.core.wsgi import WebSpark
from webspark.http.response import TextResponse
from webspark.utils.exceptions import HTTPException


class MockConfig:
    pass


class SimpleView(View):
    def handle_get(self, request):
        return TextResponse("OK")


class StartResponseMock:
    def __init__(self):
        self.status = None
        self.headers = None

    def __call__(self, status, headers):
        self.status = status
        self.headers = headers


def test_wsgi_app_dispatches_to_view():
    app = WebSpark(debug=True)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "test.com"}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("200 OK")
    assert response_body == b"OK"


def test_allowed_hosts_valid_host():
    config = MockConfig()
    config.ALLOWED_HOSTS = ["test.com"]
    app = WebSpark(config=config)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "test.com"}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("200 OK")
    assert response_body == b"OK"


def test_allowed_hosts_invalid_host():
    config = MockConfig()
    config.ALLOWED_HOSTS = ["test.com"]
    app = WebSpark(config=config)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "HTTP_HOST": "invalid.com",
        "wsgi.errors": Mock(),
    }
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter).decode()

    assert start_response.status.startswith("400 Bad Request")
    assert "Host 'invalid.com' not allowed" in response_body


def test_allowed_hosts_wildcard_subdomain():
    config = MockConfig()
    config.ALLOWED_HOSTS = [".test.com"]
    app = WebSpark(config=config)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "sub.test.com"}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("200 OK")
    assert response_body == b"OK"


def test_allowed_hosts_wildcard_root_domain():
    config = MockConfig()
    config.ALLOWED_HOSTS = [".test.com"]
    app = WebSpark(config=config)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "test.com"}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("200 OK")
    assert response_body == b"OK"


def test_allowed_hosts_wildcard_invalid_domain():
    config = MockConfig()
    config.ALLOWED_HOSTS = [".test.com"]
    app = WebSpark(config=config)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "HTTP_HOST": "invalid.com",
        "wsgi.errors": Mock(),
    }
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    b"".join(response_iter)

    assert start_response.status.startswith("400 Bad Request")


def test_allowed_hosts_debug_mode_allows_all():
    app = WebSpark(debug=True)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "any.host.com"}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("200 OK")
    assert response_body == b"OK"


def test_allowed_hosts_not_set_no_debug_denies_all():
    app = WebSpark(debug=False)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "HTTP_HOST": "any.host.com",
        "wsgi.errors": Mock(),
    }
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    b"".join(response_iter)

    assert start_response.status.startswith("400 Bad Request")


def test_allowed_hosts_star_allows_all():
    config = MockConfig()
    config.ALLOWED_HOSTS = ["*"]
    app = WebSpark(config=config, debug=False)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "any.host.com"}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("200 OK")
    assert response_body == b"OK"


def test_allowed_hosts_missing_host_header():
    app = WebSpark(debug=True)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "wsgi.errors": Mock()}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter).decode()

    assert start_response.status.startswith("400 Bad Request")
    assert "Invalid or missing host header" in response_body


def test_allowed_hosts_strips_port():
    config = MockConfig()
    config.ALLOWED_HOSTS = ["test.com"]
    app = WebSpark(config=config)
    app.add_paths([path("/", view=SimpleView.as_view())])
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "test.com:8000"}
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("200 OK")
    assert response_body == b"OK"


def test_exception_handler_catches_http_exception():
    app = WebSpark(debug=True)

    class ExceptionView(View):
        def handle_get(self, request):
            raise HTTPException("Test error", status_code=418)

    app.add_paths([path("/", view=ExceptionView.as_view())])
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "HTTP_HOST": "test.com",
        "wsgi.errors": Mock(),
    }
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter).decode()

    assert start_response.status.startswith("418 I'm a teapot")
    assert '"code":"I_AM_A_TEAPOT"' in response_body
    assert '"message":"Test error"' in response_body


def test_custom_exception_handler():
    app = WebSpark(debug=True)

    @app.handle_exception(404)
    def custom_404_handler(request, exc):
        return TextResponse("Custom Not Found", status=404)

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/not-found",
        "HTTP_HOST": "test.com",
        "wsgi.errors": Mock(),
    }
    start_response = StartResponseMock()

    response_iter = app(environ, start_response)
    response_body = b"".join(response_iter)

    assert start_response.status.startswith("404 Not Found")
    assert response_body == b"Custom Not Found"
