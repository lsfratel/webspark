import io
from unittest.mock import MagicMock, Mock

import pytest

from webspark.core.plugin import Plugin
from webspark.core.router import path
from webspark.core.views import View
from webspark.core.wsgi import WebSpark
from webspark.http.response import JsonResponse, TextResponse
from webspark.utils.exceptions import HTTPException


@pytest.fixture
def app():
    """Provides a default WebSpark app instance."""
    return WebSpark()


@pytest.fixture
def mock_env():
    """Provides a mock WSGI environment."""
    return {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": io.StringIO(),
    }


@pytest.fixture
def mock_start_response():
    """Provides a mock start_response callable."""
    return MagicMock()


class MockView(View):
    @classmethod
    def as_view(cls):
        def view_handler(request, **kwargs):
            return JsonResponse({"status": "ok"})

        view_handler.http_methods = ["get"]
        return view_handler


class MockPlugin(Plugin):
    def before_request(self, request):
        request.context["plugin_ran"] = True
        return request


def test_webspark_initialization():
    """Test WebSpark app initialization."""
    app = WebSpark(debug=True)
    assert app.debug is True
    assert app._router is not None
    assert app._plugins == []
    assert app._exceptions == {}

    plugin = MockPlugin()
    app_with_plugin = WebSpark(global_plugins=[plugin])
    assert app_with_plugin._plugins == [plugin]


def test_add_single_plugin(app):
    """Test adding a single global plugin."""
    plugin = MockPlugin()
    app.add_plugins(plugin)
    assert plugin in app._plugins


def test_add_paths_simple(app):
    """Test adding a simple list of paths."""
    app.add_paths([path("/", view=MockView.as_view())])
    assert len(app._router.routes["get"]) == 1
    assert app._router.routes["get"][0].pattern == "/"


def test_add_paths_nested(app):
    """Test adding nested lists of paths."""
    app.add_paths(
        [
            [path("/nested", view=MockView.as_view())],
            path("/simple", view=MockView.as_view()),
        ]
    )
    assert len(app._router.routes["get"]) == 2


def test_add_paths_with_children(app):
    """Test adding paths with children (grouped paths)."""
    app.add_paths(
        [
            path(
                "/api",
                children=[
                    path("/users", view=MockView.as_view()),
                    path("/posts", view=MockView.as_view()),
                ],
            )
        ]
    )
    assert len(app._router.routes["get"]) == 2
    assert app._router.routes["get"][0].pattern == "/api/users"
    assert app._router.routes["get"][1].pattern == "/api/posts"


def test_wsgi_call_successful(app, mock_env, mock_start_response):
    """Test a successful WSGI call."""

    class SuccessView(View):
        @classmethod
        def as_view(cls):
            def view_handler(request):
                return JsonResponse({"message": "Success"})

            view_handler.http_methods = ["get"]
            return view_handler

    app.add_paths([path("/", view=SuccessView.as_view())])

    body = app(mock_env, mock_start_response)

    mock_start_response.assert_called_once()
    status, headers = mock_start_response.call_args[0]
    assert status == "200 OK"
    assert ("content-type", "application/json; charset=utf-8") in headers
    assert list(body) == [b'{"message":"Success"}']


def test_wsgi_call_not_found(app, mock_env, mock_start_response):
    """Test a WSGI call that results in a 404 Not Found."""
    mock_env["PATH_INFO"] = "/not-found"
    body = app(mock_env, mock_start_response)

    mock_start_response.assert_called_once()
    status, _ = mock_start_response.call_args[0]
    assert status == "404 Not Found"
    assert b'"code":"NOT_FOUND"' in b"".join(body)


def test_wsgi_call_http_exception(app, mock_env, mock_start_response):
    """Test a WSGI call where the view raises an HTTPException."""

    class ExceptionView(View):
        def handle_get(self, request):
            raise HTTPException("Access Denied", status_code=403)

    app.add_paths([path("/", view=ExceptionView.as_view())])

    body = app(mock_env, mock_start_response)

    mock_start_response.assert_called_once()
    status, _ = mock_start_response.call_args[0]
    assert status == "403 Forbidden"
    assert b"Access Denied" in b"".join(body)


def test_wsgi_call_unhandled_exception(app, mock_env, mock_start_response):
    """Test a WSGI call with an unhandled exception."""

    class ErrorView(View):
        def handle_get(self, request):
            raise ValueError("Something went wrong")

    app.add_paths([path("/", view=ErrorView.as_view())])

    body = app(mock_env, mock_start_response)

    mock_start_response.assert_called_once()
    status, _ = mock_start_response.call_args[0]
    assert status == "500 Internal Server Error"
    assert b'"code":"INTERNAL_ERROR"' in b"".join(body)


def test_wsgi_call_unhandled_exception_debug_mode(mock_env, mock_start_response):
    """Test that debug mode writes to wsgi.errors."""
    app = WebSpark(debug=True)

    class ErrorView(View):
        def handle_get(self, request):
            raise ValueError("Debug error")

    app.add_paths([path("/", view=ErrorView.as_view())])

    app(mock_env, mock_start_response)

    errors = mock_env["wsgi.errors"].getvalue()
    assert "ValueError: Debug error" in errors


def test_custom_exception_handler(app, mock_env, mock_start_response):
    """Test a custom exception handler."""

    @app.handle_exception(404)
    def custom_not_found(request, exc):
        return TextResponse("Custom Not Found Page", status=404)

    mock_env["PATH_INFO"] = "/not-found"
    body = app(mock_env, mock_start_response)

    mock_start_response.assert_called_once()
    status, _ = mock_start_response.call_args[0]
    assert status == "404 Not Found"
    assert list(body) == [b"Custom Not Found Page"]


def test_dispatch_request_invalid_response(app, mock_env):
    """Test that dispatch_request raises ValueError for invalid response types."""

    class InvalidView(View):
        def handle_get(self, request):
            return "This is not a Response object"

    app.add_paths([path("/", view=InvalidView.as_view())])

    with pytest.raises(ValueError, match="did not return a valid Response object"):
        app.dispatch_request(mock_env)


def test_dispatch_request_with_path_params(app, mock_env):
    """Test that path parameters are correctly passed to the request."""
    mock_env["PATH_INFO"] = "/users/123"

    class UserView(View):
        @classmethod
        def as_view(cls):
            def view_handler(request):
                user_id = request.path_params.get("user_id")
                return JsonResponse({"user_id": user_id})

            view_handler.http_methods = ["get"]
            return view_handler

    app.add_paths([path("/users/:user_id", view=UserView.as_view())])

    response = app.dispatch_request(mock_env)
    assert response.body == b'{"user_id":"123"}'


def test_default_exception_handler():
    """Test the default exception handler's output."""
    app = WebSpark()
    request = Mock()
    exc = HTTPException({"field": "email", "error": "is invalid"}, status_code=400)

    response = app.default_exception_handler(request, exc)
    assert isinstance(response, JsonResponse)
    assert response.status == 400
    assert (
        b'"error":{"code":"BAD_REQUEST","message":"Invalid request.","details":{"field":"email","error":"is invalid"}}'
        in response.body
    )

    exc_500 = ValueError("A generic error")
    response_500 = app.default_exception_handler(request, exc_500)
    assert response_500.status == 500
    assert b'"code":"INTERNAL_ERROR"' in response_500.body
