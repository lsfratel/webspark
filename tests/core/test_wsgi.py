from unittest.mock import Mock

from webspark.core.trierouter import path
from webspark.core.views import View
from webspark.core.wsgi import WebSpark
from webspark.http.context import Context
from webspark.utils.exceptions import HTTPException


class MockConfig:
    pass


class SimpleView(View):
    def handle_get(self, ctx: Context):
        ctx.text("OK")


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
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "HTTP_HOST": "test.com", "wsgi.errors": Mock()}
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
    assert 'Test error' in response_body


def test_custom_exception_handler():
    app = WebSpark(debug=True)

    @app.handle_exception(404)
    def custom_404_handler(ctx, exc):
        ctx.text("Custom Not Found", status=404)

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
