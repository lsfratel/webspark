from unittest.mock import Mock

import pytest

from webspark.contrib.plugins.cors import CORSPlugin
from webspark.http import Context
from webspark.utils import HTTPException


@pytest.fixture
def cors_plugin():
    return CORSPlugin(
        allow_origins=["https://example.com", "https://api.example.com"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
        allow_credentials=True,
        max_age=86400,
    )


def test_is_origin_allowed_exact_match(cors_plugin):
    assert cors_plugin._is_origin_allowed("https://example.com")
    assert cors_plugin._is_origin_allowed("https://api.example.com")
    assert not cors_plugin._is_origin_allowed("https://evil.com")


def test_is_origin_allowed_wildcard():
    cors_plugin = CORSPlugin(allow_origins=["*"])
    assert cors_plugin._is_origin_allowed("https://example.com")
    assert cors_plugin._is_origin_allowed("https://evil.com")


def test_is_origin_allowed_pattern():
    cors_plugin = CORSPlugin(allow_origins=["https://*.example.com"])
    assert cors_plugin._is_origin_allowed("https://api.example.com")
    assert cors_plugin._is_origin_allowed("https://www.example.com")
    assert not cors_plugin._is_origin_allowed("https://evil.com")


def test_get_allow_origin_value_with_credentials(cors_plugin):
    # When allow_credentials is True, should return the actual origin
    origin = "https://example.com"
    result = cors_plugin._get_allow_origin_value(origin)
    assert result == origin


def test_get_allow_origin_value_without_credentials():
    cors_plugin = CORSPlugin(allow_origins=["*"], allow_credentials=False)
    origin = "https://example.com"
    result = cors_plugin._get_allow_origin_value(origin)
    assert result == "*"


def test_is_preflight_request(cors_plugin):
    ctx = Mock()
    ctx.method = "options"
    ctx.headers = {"access-control-request-method": "POST"}

    assert cors_plugin._is_preflight_request(ctx)

    # Not a preflight request
    ctx.method = "get"
    assert not cors_plugin._is_preflight_request(ctx)

    ctx.method = "options"
    ctx.headers = {}
    assert not cors_plugin._is_preflight_request(ctx)


def test_handle_preflight_success(cors_plugin):
    ctx = Mock(spec=Context)
    ctx.headers = {
        "access-control-request-method": "POST",
        "access-control-request-headers": "Content-Type, Authorization"
    }
    ctx.set_header = Mock()
    ctx.text = Mock()

    origin = "https://example.com"
    cors_plugin._handle_preflight(ctx, origin)

    # Verify that the correct headers were set
    ctx.set_header.assert_any_call("access-control-allow-origin", origin)
    ctx.set_header.assert_any_call("access-control-allow-credentials", "true")
    ctx.set_header.assert_any_call("access-control-max-age", "86400")
    ctx.set_header.assert_any_call("access-control-allow-methods", "GET, POST, PUT, DELETE")
    ctx.set_header.assert_any_call("access-control-allow-headers", "content-type, authorization")
    ctx.set_header.assert_any_call("vary", "origin")

    # Verify that a 204 response was sent
    ctx.text.assert_called_once_with(b"", status=204)


def test_handle_preflight_disallowed_method(cors_plugin):
    ctx = Mock(spec=Context)
    ctx.headers = {"access-control-request-method": "TRACE"}

    origin = "https://example.com"

    with pytest.raises(HTTPException) as exc_info:
        cors_plugin._handle_preflight(ctx, origin)

    assert exc_info.value.status_code == 405


def test_apply_non_cors_request(cors_plugin):
    # Mock a handler function
    def mock_handler(ctx):
        ctx.text("Hello World")

    # Create a context without an origin header (not a CORS request)
    environ = {
        "REQUEST_METHOD": "GET",
        "HTTP_HOST": "localhost:8000",
        "wsgi.url_scheme": "http"
    }
    ctx = Context(environ)

    # Apply the CORS plugin
    wrapped_handler = cors_plugin.apply(mock_handler)

    # Execute the wrapped handler
    wrapped_handler(ctx)

    # Verify that no CORS headers were added
    assert ctx.get_header("access-control-allow-origin") is None


def test_apply_cors_request_success(cors_plugin):
    # Mock a handler function
    def mock_handler(ctx):
        ctx.json({"message": "success"})

    # Create a context with an origin header (CORS request)
    environ = {
        "REQUEST_METHOD": "GET",
        "HTTP_HOST": "localhost:8000",
        "wsgi.url_scheme": "http",
        "HTTP_ORIGIN": "https://example.com"
    }
    ctx = Context(environ)

    # Apply the CORS plugin
    wrapped_handler = cors_plugin.apply(mock_handler)

    # Execute the wrapped handler
    wrapped_handler(ctx)

    # Verify that CORS headers were added
    assert ctx.get_header("access-control-allow-origin") == "https://example.com"
    assert ctx.get_header("access-control-allow-credentials") == "true"


def test_apply_cors_request_disallowed_origin(cors_plugin):
    # Mock a handler function
    def mock_handler(ctx):
        ctx.json({"message": "success"})

    # Create a context with a disallowed origin
    environ = {
        "REQUEST_METHOD": "GET",
        "HTTP_HOST": "localhost:8000",
        "wsgi.url_scheme": "http",
        "HTTP_ORIGIN": "https://evil.com"
    }
    ctx = Context(environ)

    # Apply the CORS plugin
    wrapped_handler = cors_plugin.apply(mock_handler)

    # Execute the wrapped handler and expect an exception
    with pytest.raises(HTTPException) as exc_info:
        wrapped_handler(ctx)

    assert exc_info.value.status_code == 403
