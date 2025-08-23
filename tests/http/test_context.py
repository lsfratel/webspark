import io
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from webspark.http.context import Context
from webspark.utils import HTTPException


class MockConfig:
    """Mock config class for testing."""

    MAX_BODY_SIZE = 10 * 1024 * 1024
    TRUST_PROXY = False
    TRUSTED_PROXY_LIST = None
    TRUSTED_PROXY_COUNT = 0
    SECRET = "default_secret"


class MockWebSpark:
    """Mock WebSpark instance for testing."""

    def __init__(self):
        self.config = MockConfig()


class MockView:
    """Mock view instance for testing."""

    pass


@pytest.fixture
def mock_environ():
    """Base WSGI environment for testing."""
    return {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/test",
        "QUERY_STRING": "page=1&limit=10",
        "HTTP_HOST": "example.com",
        "HTTP_USER_AGENT": "TestAgent/1.0",
        "HTTP_ACCEPT": "application/json,text/html",
        "HTTP_COOKIE": 'session="ImFiYzEyMyI="; user="ImpvaG4i"',
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": "0",
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.url_scheme": "https",
        "wsgi.input": io.BytesIO(),
        "webspark.instance": MockWebSpark(),
        "webspark.view_instance": MockView(),
    }


@pytest.fixture
def context(mock_environ):
    """Create a Context instance for testing."""
    return Context(mock_environ)


# ===========================================
# REQUEST FUNCTIONALITY TESTS
# ===========================================


def test_basic_request_properties(context):
    """Test basic request properties."""
    assert context.method == "get"
    assert context.path == "/test"
    assert context.scheme == "https"
    assert context.host == "example.com"
    assert context.is_secure is True
    assert context.ip == "127.0.0.1"
    assert context.user_agent == "TestAgent/1.0"
    assert context.accept == "application/json,text/html"


def test_query_params_parsing(context):
    """Test query parameters parsing."""
    assert context.query_params == {"page": "1", "limit": "10"}


def test_query_params_empty(mock_environ):
    """Test empty query string handling."""
    mock_environ["QUERY_STRING"] = ""
    context = Context(mock_environ)
    assert context.query_params == {}


def test_query_params_malformed(mock_environ):
    """Test malformed query string handling."""
    mock_environ["QUERY_STRING"] = "invalid%query&string%"
    context = Context(mock_environ)
    assert context.query_params == {}


def test_headers_parsing(context):
    """Test headers parsing."""
    headers = context.headers
    assert headers["host"] == "example.com"
    assert headers["user-agent"] == "TestAgent/1.0"
    assert headers["accept"] == "application/json,text/html"
    assert headers["cookie"] == 'session="ImFiYzEyMyI="; user="ImpvaG4i"'
    assert headers["content-type"] == "application/json"


def test_headers_missing_standard(mock_environ):
    """Test missing standard headers."""
    del mock_environ["HTTP_HOST"]
    del mock_environ["HTTP_USER_AGENT"]

    context = Context(mock_environ)
    assert context.host == ""
    assert context.user_agent == ""


def test_url_construction(context):
    """Test URL construction."""
    assert context.url == "https://example.com/test?page=1&limit=10"


def test_cookies_parsing(context: Context):
    """Test cookie parsing."""
    cookies = context.cookies
    assert cookies["session"] == "abc123"
    assert cookies["user"] == "john"


def test_content_type_parsing(context):
    """Test content type parsing."""
    assert context.content_type == "application/json"


def test_charset_detection_default(context):
    """Test default charset detection."""
    assert context.charset == "utf-8"


def test_charset_detection_custom(context):
    """Test custom charset detection."""
    context.environ["CONTENT_TYPE"] = "text/html; charset=iso-8859-1"
    # Reset cached property
    context.__dict__.pop("charset", None)
    assert context.charset == "iso-8859-1"


def test_content_length_valid(context):
    """Test valid content length."""
    context.environ["CONTENT_LENGTH"] = "100"
    context.__dict__.pop("content_length", None)
    assert context.content_length == 100


def test_content_length_invalid(mock_environ):
    """Test invalid content length handling."""
    mock_environ["CONTENT_LENGTH"] = "invalid"
    context = Context(mock_environ)
    assert context.content_length == 0


def test_content_length_negative(mock_environ):
    """Test negative content length handling."""
    mock_environ["CONTENT_LENGTH"] = "-100"
    context = Context(mock_environ)
    assert context.content_length == 0


def test_body_parsing_json(mock_environ):
    """Test JSON body parsing."""
    test_data = {"name": "John", "age": 30}
    json_data = json.dumps(test_data).encode()

    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(json_data)),
            "wsgi.input": io.BytesIO(json_data),
        }
    )

    context = Context(mock_environ)
    assert context.body == test_data


def test_body_parsing_form_urlencoded(mock_environ):
    """Test form URL-encoded body parsing."""
    form_data = "name=John&age=30&tags=python&tags=web"
    encoded_data = form_data.encode()

    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/x-www-form-urlencoded",
            "CONTENT_LENGTH": str(len(encoded_data)),
            "wsgi.input": io.BytesIO(encoded_data),
        }
    )

    context = Context(mock_environ)
    body = context.body
    assert body["name"] == "John"
    assert body["age"] == "30"
    assert body["tags"] == ["python", "web"]


def test_body_parsing_empty_json(mock_environ):
    """Test empty JSON body parsing."""
    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": "0",
            "wsgi.input": io.BytesIO(b""),
        }
    )

    context = Context(mock_environ)
    assert context.body == {}


def test_body_invalid_method(context):
    """Test body access with invalid method."""
    with pytest.raises(HTTPException) as exc_info:
        _ = context.body
    assert exc_info.value.status_code == 405


def test_body_too_large(mock_environ):
    """Test body size limit."""
    large_size = 20 * 1024 * 1024  # 20MB
    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(large_size),
            "wsgi.input": io.BytesIO(b"x" * 1000),
        }
    )

    context = Context(mock_environ)
    with pytest.raises(HTTPException) as exc_info:
        _ = context.body
    assert exc_info.value.status_code == 413


def test_body_missing_content_type(mock_environ):
    """Test body access without content type."""
    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_LENGTH": "10",
            "wsgi.input": io.BytesIO(b"test data"),
        }
    )
    del mock_environ["CONTENT_TYPE"]

    context = Context(mock_environ)
    with pytest.raises(HTTPException) as exc_info:
        _ = context.body
    assert exc_info.value.status_code == 400


def test_body_unsupported_content_type(mock_environ):
    """Test body access with unsupported content type."""
    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/xml",
            "CONTENT_LENGTH": "10",
            "wsgi.input": io.BytesIO(b"<test/>"),
        }
    )

    context = Context(mock_environ)
    with pytest.raises(HTTPException) as exc_info:
        _ = context.body
    assert exc_info.value.status_code == 415


def test_body_json_parsing_error(mock_environ):
    """Test JSON parsing error handling."""
    invalid_json = b'{"invalid": json}'
    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(invalid_json)),
            "wsgi.input": io.BytesIO(invalid_json),
        }
    )

    context = Context(mock_environ)
    with pytest.raises(HTTPException) as exc_info:
        _ = context.body
    assert exc_info.value.status_code == 400


def test_body_unicode_decode_error(mock_environ):
    """Test Unicode decode error handling."""
    invalid_utf8 = b"\xff\xfe\x00\x00"
    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(invalid_utf8)),
            "wsgi.input": io.BytesIO(invalid_utf8),
        }
    )

    context = Context(mock_environ)
    with pytest.raises(HTTPException) as exc_info:
        _ = context.body
    assert exc_info.value.status_code == 400


def test_path_params_default(context):
    """Test default path parameters."""
    assert context.path_params == {}


def test_path_params_setting(context):
    """Test setting path parameters."""
    context.path_params = {"id": "123", "slug": "test"}
    assert context.path_params == {"id": "123", "slug": "test"}


def test_proxy_trust_disabled(context):
    """Test proxy headers when trust is disabled."""
    context.environ["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"
    context.environ["HTTP_X_REAL_IP"] = "192.168.1.1"
    context.environ["HTTP_X_FORWARDED_PROTO"] = "https"

    # Reset cached properties
    context.__dict__.pop("ip", None)
    context.__dict__.pop("scheme", None)

    assert context.ip == "127.0.0.1"  # Uses REMOTE_ADDR
    assert context.scheme == "https"  # Uses wsgi.url_scheme


def test_proxy_trust_enabled(context):
    """Test proxy headers when trust is enabled."""
    context.webspark.config.TRUST_PROXY = True
    context.environ["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"
    context.environ["HTTP_X_FORWARDED_PROTO"] = "http"

    # Reset cached properties
    context.__dict__.pop("ip", None)
    context.__dict__.pop("scheme", None)

    assert context.ip == "192.168.1.1"
    assert context.scheme == "http"


# ===========================================
# RESPONSE FUNCTIONALITY TESTS
# ===========================================


def test_text_response(context):
    """Test text response."""
    context.text("Hello, World!", 201)

    assert context.status == 201
    assert context.response_body == "Hello, World!"
    assert context.get_header("content-type") == "text/plain; charset=utf-8"
    assert context.responded is True


def test_text_response_default_status(context):
    """Test text response with default status."""
    context.text("Hello, World!")
    assert context.status == 200


def test_json_response(context):
    """Test JSON response."""
    data = {"message": "Hello", "status": "success"}
    context.json(data, 200)

    assert context.status == 200
    assert context.response_body == data
    assert context.get_header("content-type") == "application/json; charset=utf-8"
    assert context.responded is True


def test_json_response_default_status(context):
    """Test JSON response with default status."""
    context.json({"test": "data"})
    assert context.status == 200


def test_html_response(context):
    """Test HTML response."""
    html = "<html><body><h1>Hello</h1></body></html>"
    context.html(html)

    assert context.status == 200
    assert context.response_body == html
    assert context.get_header("content-type") == "text/html; charset=utf-8"


def test_html_response_custom_status(context):
    """Test HTML response with custom status."""
    context.html("<h1>Not Found</h1>", 404)
    assert context.status == 404


def test_redirect_response_temporary(context):
    """Test temporary redirect response."""
    context.redirect("/new-path")

    assert context.status == 302
    assert context.response_body == b""
    assert context.get_header("location") == "/new-path"


def test_redirect_response_permanent(context):
    """Test permanent redirect."""
    context.redirect("/new-path", permanent=True)

    assert context.status == 301
    assert context.get_header("location") == "/new-path"


def test_error_response(context):
    """Test error response."""
    context.error("Something went wrong", 500)

    assert context.status == 500
    assert context.response_body == {"error": "Something went wrong", "status": 500}
    assert context.get_header("content-type") == "application/json; charset=utf-8"


def test_error_response_default_status(context):
    """Test error response with default status."""
    context.error("Internal Error")
    assert context.status == 500


def test_header_set_and_get(context):
    """Test setting and getting headers."""
    context.set_header("X-Custom", "test-value")
    assert context.get_header("x-custom") == "test-value"
    assert context.get_header("X-Custom") == "test-value"  # Case insensitive


def test_header_get_nonexistent(context):
    """Test getting non-existent header."""
    assert context.get_header("non-existent") is None


def test_header_delete(context):
    """Test deleting headers."""
    context.set_header("X-Custom", "test-value")
    context.delete_header("X-Custom")
    assert context.get_header("x-custom") is None


def test_cookie_setting(context):
    """Test cookie setting."""
    context.set_cookie("session", "abc123", max_age=3600)
    context.set_cookie("user", "john", secure=True, http_only=False)

    assert len(context._cookies) == 2


def test_cookie_deletion(context):
    """Test cookie deletion."""
    context.delete_cookie("old_session")

    # Should create a cookie with negative max_age
    assert len(context._cookies) == 1


def test_response_state_tracking(context):
    """Test response state tracking."""
    assert context.responded is False

    context.json({"test": "data"})
    assert context.responded is True


def test_response_reset(context):
    """Test response reset functionality."""
    context.json({"test": "data"})
    context.set_header("X-Custom", "value")
    context.set_cookie("test", "value")

    assert context.responded is True
    assert len(context.response_headers) > 0
    assert len(context._cookies) > 0

    context.reset_response()

    assert context.status == 200
    assert context.response_body == b""
    assert context.responded is False
    assert len(context.response_headers) == 0
    assert len(context._cookies) == 0


def test_assert_not_responded_success(context):
    """Test assertion when not responded."""
    context.assert_not_responded()  # Should not raise


def test_assert_not_responded_failure(context):
    """Test assertion when already responded."""
    context.text("Hello")

    with pytest.raises(RuntimeError, match="Response has already been set"):
        context.assert_not_responded()


# ===========================================
# STREAMING FUNCTIONALITY TESTS
# ===========================================


def test_stream_bytes_basic(context):
    """Test streaming bytes."""
    data = b"Hello, World!"
    context.stream(data)

    assert context.status == 200
    assert context.response_body == [data]
    assert context.get_header("content-length") == str(len(data))
    assert context.get_header("accept-ranges") == "bytes"


def test_stream_bytes_with_range(context):
    """Test streaming bytes with range header."""
    data = b"Hello, World! This is a test."
    context.headers["range"] = "bytes=0-4"
    context.stream(data)

    assert context.status == 206
    assert context.response_body == [b"Hello"]
    assert "content-range" in context.response_headers
    assert context.response_headers["content-range"] == "bytes 0-4/29"


def test_stream_bytes_custom_content_type(context):
    """Test streaming bytes with custom content type."""
    data = b"Custom data"
    context.stream(data, content_type="text/plain")

    assert context.get_header("content-type") == "text/plain"


def test_stream_file_not_found(context):
    """Test streaming non-existent file."""
    with pytest.raises(HTTPException) as exc_info:
        context.stream("/non/existent/file.txt")
    assert exc_info.value.status_code == 404


def test_stream_file_success(context):
    """Test streaming existing file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        test_content = b"This is test file content."
        tmp.write(test_content)
        tmp.flush()

        try:
            context.stream(tmp.name, download="test.txt")

            assert context.status == 200
            assert (
                context.get_header("content-disposition")
                == 'attachment; filename="test.txt"'
            )
            assert "content-length" in context.response_headers
            assert "last-modified" in context.response_headers
            assert "date" in context.response_headers

            # Test file iterator
            content = b"".join(context.response_body)
            assert content == test_content

        finally:
            os.unlink(tmp.name)


def test_stream_file_with_range(context):
    """Test streaming file with range header."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        test_content = b"0123456789" * 10  # 100 bytes
        tmp.write(test_content)
        tmp.flush()
        context.headers["range"] = "bytes=10-19"

        try:
            context.stream(tmp.name)

            assert context.status == 206
            assert "content-range" in context.response_headers
            assert context.response_headers["content-range"] == "bytes 10-19/100"

            # Test partial content
            content = b"".join(context.response_body)
            assert content == test_content[10:20]

        finally:
            os.unlink(tmp.name)


def test_stream_file_no_permission():
    """Test streaming file without read permission."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test content")
        tmp.flush()

        try:
            # Change file permissions to no read
            os.chmod(tmp.name, 0o000)

            context = Context(
                {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/test",
                    "webspark.instance": MockWebSpark(),
                    "webspark.view_instance": MockView(),
                }
            )

            with pytest.raises(HTTPException) as exc_info:
                context.stream(tmp.name)
            assert exc_info.value.status_code == 403

        finally:
            os.chmod(tmp.name, 0o644)  # Restore permissions for deletion
            os.unlink(tmp.name)


def test_stream_iterable(context):
    """Test streaming iterable."""

    def data_generator():
        for i in range(3):
            yield f"chunk {i}\n".encode()

    context.stream(data_generator())

    assert context.status == 200
    assert context.get_header("content-type") == "application/octet-stream"


def test_stream_list_iterable(context):
    """Test streaming list iterable."""
    data_chunks = [b"chunk1", b"chunk2", b"chunk3"]
    context.stream(data_chunks)

    assert context.status == 200
    assert context.response_body == data_chunks


def test_parse_range_valid(context):
    """Test valid range header parsing."""
    start, end = context._parse_range("bytes=10-20", 100)
    assert start == 10
    assert end == 20


def test_parse_range_open_end(context):
    """Test range header with open end."""
    start, end = context._parse_range("bytes=50-", 100)
    assert start == 50
    assert end == 99


def test_parse_range_from_beginning(context):
    """Test range header from beginning."""
    start, end = context._parse_range("bytes=-20", 100)
    assert start == 0
    assert end == 20


def test_parse_range_invalid_unit(context):
    """Test invalid range unit."""
    with pytest.raises(HTTPException) as exc_info:
        context._parse_range("invalid=10-20", 100)
    assert exc_info.value.status_code == 416


def test_parse_range_invalid_format(context):
    """Test invalid range format."""
    with pytest.raises(HTTPException) as exc_info:
        context._parse_range("bytes=invalid", 100)
    assert exc_info.value.status_code == 416


def test_parse_range_out_of_bounds(context):
    """Test out of bounds range."""
    with pytest.raises(HTTPException) as exc_info:
        context._parse_range("bytes=200-300", 100)
    assert exc_info.value.status_code == 416


def test_mime_type_detection_json(context):
    """Test JSON MIME type detection."""
    mime_type = context._detect_stream_mimetype("test.json", None)
    assert mime_type == "application/json"


def test_mime_type_detection_explicit(context):
    """Test explicit content type override."""
    mime_type = context._detect_stream_mimetype("test.unknown", "text/plain")
    assert mime_type == "text/plain"


def test_mime_type_detection_fallback(context):
    """Test MIME type fallback."""
    mime_type = context._detect_stream_mimetype("test", None)
    assert mime_type == "application/octet-stream"


def test_mime_type_detection_text_charset(context):
    """Test charset addition for text types."""
    mime_type = context._detect_stream_mimetype("test.txt", None)
    assert "charset=utf-8" in mime_type


def test_mime_type_detection_javascript_charset(context):
    """Test charset addition for JavaScript."""
    mime_type = context._detect_stream_mimetype("test.js", None)
    assert "charset=utf-8" in mime_type


def test_mime_type_detection_gzip_encoding(context):
    """Test gzip encoding detection."""
    mime_type = context._detect_stream_mimetype("test.tar.gz", None)
    assert mime_type == "application/gzip"


# ===========================================
# CONVENIENCE METHODS TESTS
# ===========================================


def test_is_ajax_false(context):
    """Test AJAX detection when not AJAX."""
    assert context.is_ajax() is False


def test_is_ajax_true(context):
    """Test AJAX detection when is AJAX."""
    context.environ["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
    # Reset cached property
    context.__dict__.pop("headers", None)
    assert context.is_ajax() is True


def test_accepts_json(context):
    """Test JSON acceptance."""
    assert context.accepts("application/json") is True


def test_accepts_html(context):
    """Test HTML acceptance."""
    assert context.accepts("text/html") is True


def test_accepts_not_supported(context):
    """Test unsupported content type."""
    assert context.accepts("application/xml") is False


def test_accepts_wildcard(context):
    """Test wildcard acceptance."""
    context.environ["HTTP_ACCEPT"] = "*/*"
    context.__dict__.pop("accept", None)

    assert context.accepts("application/xml") is True


def test_wants_json_true(context):
    """Test JSON preference detection."""
    assert context.wants_json() is True


def test_wants_html_true(context):
    """Test HTML preference detection."""
    assert context.wants_html() is True


def test_wants_json_false(context):
    """Test JSON preference when not wanted."""
    context.environ["HTTP_ACCEPT"] = "text/plain"
    context.__dict__.pop("accept", None)

    assert context.wants_json() is False


def test_wants_html_false(context):
    """Test HTML preference when not wanted."""
    context.environ["HTTP_ACCEPT"] = "application/xml"
    context.__dict__.pop("accept", None)

    assert context.wants_html() is False


# ===========================================
# WSGI CONVERSION TESTS
# ===========================================


def test_regular_response_wsgi(context):
    """Test WSGI conversion for regular response."""
    context.json({"message": "hello"})

    status, headers, body = context.as_wsgi()

    assert status == "200 OK"
    header_dict = dict(headers)
    assert header_dict["content-type"] == "application/json; charset=utf-8"
    assert "Content-Length" in header_dict

    body_data = b"".join(body)
    assert json.loads(body_data.decode()) == {"message": "hello"}


def test_streaming_response_wsgi(context):
    """Test WSGI conversion for streaming response."""
    test_data = [b"chunk1", b"chunk2", b"chunk3"]
    context.stream(test_data)

    status, headers, body = context.as_wsgi()

    assert status == "200 OK"
    assert body == test_data


def test_wsgi_with_cookies(context):
    """Test WSGI conversion with cookies."""
    context.text("Hello")
    context.set_cookie("session", "abc123")
    context.set_cookie("user", "john")

    status, headers, body = context.as_wsgi()

    # Should have Set-Cookie headers
    cookie_headers = [h for h in headers if h[0] == "Set-Cookie"]
    assert len(cookie_headers) == 2


def test_wsgi_status_codes(context):
    """Test various status codes in WSGI."""
    context.text("Not Found", 404)
    status, headers, body = context.as_wsgi()
    assert status == "404 Not Found"

    context.reset_response()
    context.error("Internal Error", 500)
    status, headers, body = context.as_wsgi()
    assert status == "500 Internal Server Error"


def test_wsgi_unknown_status_code(context):
    """Test unknown status code in WSGI."""
    context.status = 999
    context.response_body = "Unknown"

    status, headers, body = context.as_wsgi()
    assert status == "999 Unknown"


# ===========================================
# INTEGRATION AND EDGE CASE TESTS
# ===========================================


def test_context_lifecycle():
    """Test full context lifecycle."""
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/api/users",
        "QUERY_STRING": "include=profile",
        "HTTP_ACCEPT": "application/json",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b'{"name": "John"}'),
        "webspark.instance": MockWebSpark(),
        "webspark.view_instance": MockView(),
    }

    # Create context
    ctx = Context(environ)

    # Check request data
    assert ctx.method == "post"
    assert ctx.path == "/api/users"
    assert ctx.query_params == {"include": "profile"}

    # Set response
    ctx.json({"id": 1, "name": "John"}, 201)
    ctx.set_cookie("session", "new_session")

    # Convert to WSGI
    status, headers, body = ctx.as_wsgi()

    assert status == "201 Created"
    assert any(h[0] == "Set-Cookie" for h in headers)

    body_data = b"".join(body)
    response_data = json.loads(body_data.decode())
    assert response_data == {"id": 1, "name": "John"}


def test_context_multiple_operations(context):
    """Test multiple operations on same context."""
    # Set initial response
    context.text("Hello")
    assert context.responded is True

    # Reset and set new response
    context.reset_response()
    assert context.responded is False

    context.json({"message": "world"})
    assert context.responded is True
    assert context.status == 200


def test_context_headers_case_insensitive(context):
    """Test case insensitive header handling."""
    context.set_header("Content-Type", "text/plain")
    context.set_header("x-custom-header", "value1")
    context.set_header("X-Another-Header", "value2")

    assert context.get_header("content-type") == "text/plain"
    assert context.get_header("Content-Type") == "text/plain"
    assert context.get_header("CONTENT-TYPE") == "text/plain"

    assert context.get_header("x-custom-header") == "value1"
    assert context.get_header("X-Custom-Header") == "value1"


def test_context_body_caching(mock_environ):
    """Test that body parsing is cached."""
    test_data = {"cached": True}
    json_data = json.dumps(test_data).encode()

    mock_environ.update(
        {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(json_data)),
            "wsgi.input": io.BytesIO(json_data),
        }
    )

    context = Context(mock_environ)

    # First access
    body1 = context.body
    # Second access should return cached result
    body2 = context.body

    assert body1 is body2
    assert body1 == test_data


def test_context_files_empty_for_non_multipart(context):
    """Test that files is empty for non-multipart requests."""
    assert context.files == {}


def test_context_webspark_and_view_access(context):
    """Test access to WebSpark instance and view."""
    assert isinstance(context.webspark, MockWebSpark)
    assert isinstance(context.view_instance, MockView)


def test_context_max_body_size_config(context):
    """Test max body size from config."""
    assert context.max_body_size == 10 * 1024 * 1024

    # Test custom config
    context.webspark.config.MAX_BODY_SIZE = 5 * 1024 * 1024
    context.__dict__.pop("max_body_size", None)  # Reset cached property
    assert context.max_body_size == 5 * 1024 * 1024


def test_context_ip_with_trusted_proxy_list(context):
    """Test IP detection with trusted proxy list."""
    context.webspark.config.TRUST_PROXY = True
    context.webspark.config.TRUSTED_PROXY_LIST = ["10.0.0.1", "192.168.1.1"]

    context.environ["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 192.168.1.1"
    context.environ["REMOTE_ADDR"] = "192.168.1.1"

    context.__dict__.pop("ip", None)

    assert context.ip == "203.0.113.1"


def test_context_ip_with_proxy_count(context: Context):
    """Test IP detection with trusted proxy count."""
    context.webspark.config.TRUST_PROXY = True
    context.webspark.config.TRUSTED_PROXY_COUNT = 1

    context.environ["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 192.168.1.1"
    context.environ["REMOTE_ADDR"] = "10.0.0.1"

    context.__dict__.pop("ip", None)

    assert context.ip == "192.168.1.1"


def test_context_ip_with_x_real_ip(context):
    """Test IP detection with X-Real-IP header."""
    context.webspark.config.TRUST_PROXY = True
    context.environ["HTTP_X_REAL_IP"] = "203.0.113.1"

    context.__dict__.pop("ip", None)

    assert context.ip == "203.0.113.1"


def test_context_scheme_with_forwarded_proto(context):
    """Test scheme detection with X-Forwarded-Proto."""
    context.webspark.config.TRUST_PROXY = True
    context.environ["HTTP_X_FORWARDED_PROTO"] = "http, https"

    context.__dict__.pop("scheme", None)

    assert context.scheme == "http"  # Takes first value


def test_context_host_with_forwarded_host(context):
    """Test host detection with X-Forwarded-Host."""
    context.webspark.config.TRUST_PROXY = True
    context.environ["HTTP_X_FORWARDED_HOST"] = "api.example.com, proxy.example.com"

    context.__dict__.pop("host", None)

    assert context.host == "api.example.com"


def test_context_url_without_host(mock_environ):
    """Test URL construction without host."""
    mock_environ.pop("HTTP_HOST", None)
    context = Context(mock_environ)

    assert context.url == "/test"


def test_context_url_without_query_string(mock_environ):
    """Test URL construction without query string."""
    mock_environ["QUERY_STRING"] = ""
    context = Context(mock_environ)

    expected_url = "https://example.com/test"
    assert context.url == expected_url


def test_context_body_bytes_conversion(context):
    """Test _to_bytes method with different input types."""
    # Test bytes
    assert context._to_bytes(b"hello") == b"hello"

    # Test string
    assert context._to_bytes("hello") == b"hello"

    # Test object with __bytes__
    class BytesObject:
        def __bytes__(self):
            return b"custom bytes"

    assert context._to_bytes(BytesObject()) == b"custom bytes"

    # Test JSON serialization
    context.set_header("content-type", "application/json")
    result = context._to_bytes({"key": "value"})
    assert json.loads(result.decode()) == {"key": "value"}

    # Test fallback to string
    context.response_headers.clear()
    assert context._to_bytes(42) == b"42"


def test_context_stream_custom_chunk_size(context):
    """Test streaming with custom chunk size."""
    data = b"x" * 1000
    context.stream(data, chunk_size=100)

    assert context.chunk_size == 100


def test_context_file_iterator_edge_cases(context):
    """Test file iterator edge cases."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        test_content = b"0123456789"
        tmp.write(test_content)
        tmp.flush()

        try:
            context.file_path = tmp.name
            context.chunk_size = 3

            # Test reading from middle to end
            chunks = list(context._file_iterator(3, 7))
            assert b"".join(chunks) == b"34567"

            # Test reading beyond file end
            chunks = list(context._file_iterator(5, 20))
            assert b"".join(chunks) == b"56789"

        finally:
            os.unlink(tmp.name)


def test_context_multipart_cleanup():
    """Test multipart parser cleanup."""
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "multipart/form-data; boundary=test",
        "CONTENT_LENGTH": "100",
        "wsgi.input": io.BytesIO(
            b'--test\r\nContent-Disposition: form-data; name="test"\r\n\r\nvalue\r\n--test--\r\n'
        ),
        "webspark.instance": MockWebSpark(),
        "webspark.view_instance": MockView(),
    }

    context = Context(environ)

    # Access files to trigger multipart parsing
    try:
        _ = context.files
    except Exception:
        # Multipart parsing might fail with mock data, but we test cleanup
        pass

    # Test that __del__ doesn't raise errors
    del context


def test_context_response_body_iteration():
    """Test response body as iteration for streaming."""
    context = Context(
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "webspark.instance": MockWebSpark(),
            "webspark.view_instance": MockView(),
        }
    )

    def generator():
        yield b"chunk1"
        yield b"chunk2"
        yield b"chunk3"

    context.stream(generator())

    # Test that response body is iterable
    chunks = list(context.response_body)
    assert chunks == [b"chunk1", b"chunk2", b"chunk3"]


def test_context_stream_status_override(context):
    """Test streaming with custom status code."""
    context.stream(b"test data", status=206)
    assert context.status == 206


def test_context_error_preserves_json_content_type(context):
    """Test that error responses use JSON content type."""
    context.error("Test error", 400)

    assert context.get_header("content-type") == "application/json; charset=utf-8"
    assert context.response_body == {"error": "Test error", "status": 400}


def test_context_multiple_cookie_operations(context):
    """Test multiple cookie operations."""
    context.set_cookie("session", "abc123")
    context.set_cookie("user", "john", secure=True)
    context.set_cookie("temp", "value", max_age=60)
    context.delete_cookie("old_cookie")

    assert len(context._cookies) == 4  # 3 set + 1 delete


def test_context_header_operations_preserve_response_state(context):
    """Test that header operations don't interfere with response state."""
    context.json({"test": "data"})
    original_body = context.response_body

    context.set_header("X-Custom", "value")
    context.delete_header("X-Custom")

    # Body should remain unchanged
    assert context.response_body is original_body
    assert context.responded is True


def test_context_range_parsing_edge_cases(context):
    """Test range parsing edge cases."""
    # Test suffix range
    start, end = context._parse_range("bytes=-10", 100)
    assert start == 0
    assert end == 10

    # Test range at file boundary
    start, end = context._parse_range("bytes=99-200", 100)
    assert start == 99
    assert end == 99

    # Test single byte range
    start, end = context._parse_range("bytes=50-50", 100)
    assert start == 50
    assert end == 50


def test_context_mime_type_with_encoding(context):
    """Test MIME type detection with various encodings."""
    # Test compressed file
    mime_type = context._detect_stream_mimetype("test.txt.gz", None)
    assert mime_type == "application/gzip"

    # Test other encoding
    with patch("mimetypes.guess_type", return_value=("text/plain", "compress")):
        mime_type = context._detect_stream_mimetype("test.Z", None)
        assert mime_type == "application/x-compress"


def test_context_accepts_case_insensitive(context):
    """Test accepts method is case insensitive."""
    assert context.accepts("APPLICATION/JSON") is True
    assert context.accepts("Text/HTML") is True


def test_context_large_file_streaming():
    """Test streaming large files efficiently."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        # Create a larger test file
        chunk_data = b"x" * 1024  # 1KB chunk
        for _ in range(100):  # 100KB total
            tmp.write(chunk_data)
        tmp.flush()

        try:
            context = Context(
                {
                    "REQUEST_METHOD": "GET",
                    "PATH_INFO": "/test",
                    "webspark.instance": MockWebSpark(),
                    "webspark.view_instance": MockView(),
                }
            )

            context.stream(tmp.name, chunk_size=4096)

            # Verify we can iterate through all chunks
            total_size = 0
            for chunk in context.response_body:
                total_size += len(chunk)

            assert total_size == 100 * 1024

        finally:
            os.unlink(tmp.name)


def test_context_empty_wsgi_input(mock_environ):
    """Test handling of empty wsgi.input."""
    mock_environ["wsgi.input"] = io.BytesIO()
    mock_environ["REQUEST_METHOD"] = "POST"
    mock_environ["CONTENT_TYPE"] = "application/json"
    mock_environ["CONTENT_LENGTH"] = "0"

    context = Context(mock_environ)
    assert context.body == {}


def test_context_forwarded_ips_empty_list(context):
    """Test _get_forwarded_ips with no forwarded headers."""
    context.environ.pop("HTTP_X_FORWARDED_FOR", None)
    ips = context._get_forwarded_ips()
    assert "127.0.0.1" in ips  # Should include REMOTE_ADDR


def test_context_forwarded_ips_no_remote_addr(context):
    """Test _get_forwarded_ips without REMOTE_ADDR."""
    context.environ["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"
    context.environ.pop("REMOTE_ADDR", None)

    ips = context._get_forwarded_ips()
    assert ips == ["192.168.1.1", "10.0.0.1"]


# ===========================================
# PERFORMANCE AND MEMORY TESTS
# ===========================================


def test_context_cached_properties_performance():
    """Test that cached properties are actually cached."""
    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": "/test",
        "QUERY_STRING": "a=1&b=2&c=3&d=4&e=5",
        "HTTP_HOST": "example.com",
        "webspark.instance": MockWebSpark(),
        "webspark.view_instance": MockView(),
    }

    context = Context(environ)

    # First access should parse
    query1 = context.query_params
    headers1 = context.headers

    # Second access should return cached
    query2 = context.query_params
    headers2 = context.headers

    # Should be the same object (cached)
    assert query1 is query2
    assert headers1 is headers2


def test_context_memory_cleanup():
    """Test that context properly cleans up resources."""
    context = Context(
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/test",
            "webspark.instance": MockWebSpark(),
            "webspark.view_instance": MockView(),
        }
    )

    # Set some data
    context.response_body = b"x" * 10000  # 10KB
    context.set_header("X-Large", "x" * 1000)

    # Reset should clear everything
    context.reset_response()

    assert context.response_body == b""
    assert len(context.response_headers) == 0
    assert len(context._cookies) == 0
