import json
from unittest.mock import mock_open, patch

import pytest

from webspark.http.response import (
    HTMLResponse,
    JsonResponse,
    RedirectResponse,
    Response,
    StreamResponse,
    TextResponse,
)
from webspark.utils.exceptions import HTTPException


def test_response_initialization():
    response = Response()

    assert response.body == b""
    assert response.status == 200
    assert response.charset == "utf-8"
    assert response.headers == {}
    assert response._cookies == []


def test_response_initialization_with_params():
    headers = {"Content-Type": "text/plain", "X-Custom": "value"}
    response = Response(
        body="Hello, World!",
        status=201,
        headers=headers,
        content_type="text/html",
        charset="latin1",
    )

    assert response.body == "Hello, World!"
    assert response.status == 201
    assert response.charset == "latin1"
    assert response.headers == {"content-type": "text/html", "x-custom": "value"}


def test_response_invalid_status_code():
    with pytest.raises(ValueError, match="Invalid HTTP status code: 999"):
        Response(status=999)


def test_response_set_cookie():
    response = Response()
    response.set_cookie("session_id", "abc123", path="/", max_age=3600)

    assert len(response._cookies) == 1
    assert "session_id" in response._cookies[0]
    assert "abc123" in response._cookies[0]


def test_response_delete_cookie():
    response = Response()
    response.delete_cookie("session_id")

    assert len(response._cookies) == 1
    assert "session_id" in response._cookies[0]
    assert "max-age=-1" in response._cookies[0].lower()


def test_response_set_header():
    response = Response()
    response.set_header("Content-Type", "application/json")

    assert response.headers["content-type"] == "application/json"


def test_response_get_header():
    response = Response(headers={"Content-Type": "application/json"})

    assert response.get_header("Content-Type") == "application/json"
    assert response.get_header("content-type") == "application/json"
    assert response.get_header("X-Non-Existent") is None


def test_response_delete_header():
    response = Response(
        headers={"Content-Type": "application/json", "X-Custom": "value"}
    )
    response.delete_header("Content-Type")

    assert "content-type" not in response.headers
    assert "x-custom" in response.headers


def test_response_body_bytes_cached_property():
    response = Response(body="Hello, World!")

    body_bytes = response._body_bytes
    assert isinstance(body_bytes, bytes)
    assert body_bytes == b"Hello, World!"

    assert response._body_bytes is body_bytes


def test_response_to_bytes_with_bytes():
    response = Response()
    result = response._to_bytes(b"test bytes")

    assert isinstance(result, bytes)
    assert result == b"test bytes"


def test_response_to_bytes_with_string():
    response = Response()
    result = response._to_bytes("test string")

    assert isinstance(result, bytes)
    assert result == b"test string"


def test_response_to_bytes_with_string_and_charset():
    response = Response(charset="utf-16")
    result = response._to_bytes("test string")

    assert isinstance(result, bytes)
    assert result == "test string".encode("utf-16")


def test_response_to_bytes_with_object_with_bytes_method():
    class BytesObject:
        def __bytes__(self):
            return b"custom bytes"

    response = Response()
    result = response._to_bytes(BytesObject())

    assert isinstance(result, bytes)
    assert result == b"custom bytes"


def test_response_to_bytes_with_generic_object():
    response = Response()
    result = response._to_bytes(123)

    assert isinstance(result, bytes)
    assert result == b"123"


def test_response_as_wsgi():
    response = Response(body="Hello, World!", status=200)
    status_str, headers_list, body_iter = response.as_wsgi()

    assert status_str == "200 OK"
    assert ("Content-Length", "13") in headers_list
    assert body_iter == [b"Hello, World!"]


def test_response_as_wsgi_with_custom_headers():
    response = Response(
        body="Hello, World!",
        status=200,
        headers={"Content-Type": "text/plain", "X-Custom": "value"},
    )
    status_str, headers_list, body_iter = response.as_wsgi()

    assert status_str == "200 OK"
    assert ("content-type", "text/plain") in headers_list
    assert ("x-custom", "value") in headers_list
    assert ("Content-Length", "13") in headers_list
    assert body_iter == [b"Hello, World!"]


def test_response_as_wsgi_with_cookies():
    response = Response(body="Hello, World!")
    response.set_cookie("session_id", "abc123")
    status_str, headers_list, body_iter = response.as_wsgi()

    assert status_str == "200 OK"
    assert any("Set-Cookie" in header[0] for header in headers_list)
    assert body_iter == [b"Hello, World!"]


def test_text_response():
    response = TextResponse("Hello, World!", status=200)

    assert response.body == "Hello, World!"
    assert response.status == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


def test_json_response():
    data = {"message": "Hello, World!", "status": "success"}
    response = JsonResponse(data, status=200)

    assert response.status == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"

    body_bytes = response._body_bytes
    decoded_data = json.loads(body_bytes.decode("utf-8"))
    assert decoded_data == data


def test_html_response():
    html = "<html><body><h1>Hello, World!</h1></body></html>"
    response = HTMLResponse(html, status=200)

    assert response.body == html
    assert response.status == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_redirect_response_temporary():
    url = "/new-location"
    response = RedirectResponse(url)

    assert response.status == 302
    assert response.headers["location"] == url


def test_redirect_response_permanent():
    url = "/new-home"
    response = RedirectResponse(url, permanent=True)

    assert response.status == 301
    assert response.headers["location"] == url


def test_stream_response_with_bytes():
    content = b"file content"
    response = StreamResponse(
        content, status=200, content_type="application/octet-stream"
    )

    assert response.body == [content]
    assert response.status == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-length"] == "12"


def test_stream_response_with_string_dont_exists():
    content = "nonexistent_file"

    with pytest.raises(HTTPException):
        _ = StreamResponse(content, status=200)


def test_stream_response_with_pathlike_dont_exists():
    from pathlib import Path

    content = Path("/tmp/test.txt")
    with pytest.raises(HTTPException):
        _ = StreamResponse(content, status=200)


@patch("builtins.open", new_callable=mock_open, read_data=b"chunk1chunk2")
def test_stream_response_file_iterator(mock_file):
    response = StreamResponse("tests/http/test_cookie.py", status=200, chunk_size=6)

    chunks = list(response.file_iterator())

    assert len(chunks) == 2
    assert chunks[0] == b"chunk1"
    assert chunks[1] == b"chunk2"


def test_stream_response_as_wsgi():
    content = b"file content"
    response = StreamResponse(content, status=200)
    status_str, headers_list, body_iter = response.as_wsgi()

    assert status_str == "200 OK"
    assert body_iter == [content]


def test_response_as_wsgi_with_unknown_status():
    response = Response(body="Hello, World!", status=299)
    status_str, headers_list, body_iter = response.as_wsgi()

    assert status_str == "299 Unknown"
    assert body_iter == [b"Hello, World!"]


def test_response_as_wsgi_content_length_already_set():
    response = Response(body="Hello, World!", headers={"Content-Length": "13"})
    status_str, headers_list, body_iter = response.as_wsgi()

    content_length_headers = [
        h for h in headers_list if h[0].lower() == "content-length"
    ]
    assert len(content_length_headers) == 1
    assert content_length_headers[0][1] == "13"


def test_stream_response_with_content_type():
    response = StreamResponse(b"content", status=200, content_type="text/csv")

    assert response.headers["content-type"] == "text/csv"


def test_response_set_header_case_insensitive():
    response = Response()
    response.set_header("Content-Type", "application/json")
    response.set_header("content-type", "text/html")

    assert response.headers["content-type"] == "text/html"


def test_response_get_header_case_insensitive():
    response = Response(headers={"Content-Type": "application/json"})

    assert response.get_header("Content-Type") == "application/json"
    assert response.get_header("content-type") == "application/json"
    assert response.get_header("CONTENT-TYPE") == "application/json"


def test_response_delete_header_case_insensitive():
    response = Response(
        headers={"Content-Type": "application/json", "X-Custom": "value"}
    )
    response.delete_header("CONTENT-TYPE")

    assert "content-type" not in response.headers
    assert "x-custom" in response.headers


def test_stream_response_with_iterator():
    def content_generator():
        yield b"chunk1"
        yield b"chunk2"

    gen = content_generator()
    response = StreamResponse(gen, status=200)

    assert response.body is gen
    assert response.headers["content-type"] == "application/octet-stream"


def test_response_body_bytes_cache_clearing():
    response = Response(body="Hello, World!")

    first_access = response._body_bytes
    assert first_access is response._body_bytes

    response.set_header("X-Test", "value")


def test_response_body_bytes_cache_clearing_on_delete():
    response = Response(body="Hello, World!", headers={"X-Test": "value"})

    first_access = response._body_bytes
    assert first_access is response._body_bytes

    response.delete_header("X-Test")


def test_response_body_bytes_cache_clearing_on_set_cookie():
    response = Response(body="Hello, World!")

    first_access = response._body_bytes
    assert first_access is response._body_bytes

    response.set_cookie("session_id", "abc123")


def test_response_body_bytes_cache_clearing_on_delete_cookie():
    response = Response(body="Hello, World!")

    first_access = response._body_bytes
    assert first_access is response._body_bytes

    response.delete_cookie("session_id")


def test_stream_response_file_headers_text(tmp_path):
    data = b"hello world"
    p = tmp_path / "sample.txt"
    p.write_bytes(data)

    response = StreamResponse(str(p))

    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-length"] == str(len(data))
    assert "last-modified" in response.headers
    assert "date" in response.headers


def test_stream_response_file_download_header(tmp_path):
    p = tmp_path / "file.bin"
    p.write_bytes(b"x" * 10)

    response = StreamResponse(str(p), download="myname.bin")

    assert (
        response.headers["content-disposition"] == 'attachment; filename="myname.bin"'
    )


def test_stream_response_file_mimetype_gzip(tmp_path):
    p = tmp_path / "archive.gz"
    p.write_bytes(b"not a real gzip, but extension is enough")

    response = StreamResponse(str(p))

    assert response.headers["content-type"] == "application/gzip"


def test_stream_response_file_custom_content_type(tmp_path):
    p = tmp_path / "index.html"
    p.write_text("<h1>hi</h1>", encoding="utf-8")

    response = StreamResponse(str(p), content_type="text/html")

    assert response.headers["content-type"] == "text/html"


def test_stream_response_file_javascript_charset_added(tmp_path):
    p = tmp_path / "script.js"
    p.write_text("console.log('hi');", encoding="utf-8")

    response = StreamResponse(str(p))

    ct = response.headers["content-type"]
    assert ct.endswith("; charset=utf-8")
    assert "javascript" in ct


def test_stream_response_as_wsgi_file_body_iterates_content(tmp_path):
    data = b"chunk1chunk2"
    p = tmp_path / "payload.bin"
    p.write_bytes(data)

    response = StreamResponse(str(p), chunk_size=6)
    status_str, headers_list, body_iter = response.as_wsgi()

    assert status_str == "200 OK"
    collected = b"".join(body_iter)
    assert collected == data


def test_stream_response_bytes_with_range():
    content = b"abcdefghij"
    response = StreamResponse(content, range_header="bytes=2-5")

    assert response.status == 206
    assert response.body == [b"cdef"]
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.headers["content-length"] == "4"


def test_stream_response_bytes_with_open_ended_range():
    content = b"abcdefghij"
    response = StreamResponse(content, range_header="bytes=5-")

    assert response.status == 206
    assert response.body == [b"fghij"]
    assert response.headers["content-range"] == "bytes 5-9/10"
    assert response.headers["content-length"] == "5"


def test_stream_response_bytes_with_invalid_range():
    content = b"abcdefghij"
    with pytest.raises(HTTPException) as excinfo:
        StreamResponse(content, range_header="bytes=20-30")

    assert excinfo.value.status_code == 416


def test_stream_response_file_with_range(tmp_path):
    data = b"0123456789"
    p = tmp_path / "rangefile.bin"
    p.write_bytes(data)

    response = StreamResponse(str(p), range_header="bytes=2-5")

    assert response.status == 206
    chunks = list(response.body)
    assert b"".join(chunks) == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/10"
    assert response.headers["content-length"] == "4"


def test_stream_response_file_with_open_ended_range(tmp_path):
    data = b"0123456789"
    p = tmp_path / "rangefile2.bin"
    p.write_bytes(data)

    response = StreamResponse(str(p), range_header="bytes=7-")

    assert response.status == 206
    collected = b"".join(response.body)
    assert collected == b"789"
    assert response.headers["content-range"] == "bytes 7-9/10"
    assert response.headers["content-length"] == "3"


def test_stream_response_file_with_invalid_range(tmp_path):
    data = b"0123456789"
    p = tmp_path / "bad_range.bin"
    p.write_bytes(data)

    with pytest.raises(HTTPException) as excinfo:
        StreamResponse(str(p), range_header="bytes=50-60")

    assert excinfo.value.status_code == 416
