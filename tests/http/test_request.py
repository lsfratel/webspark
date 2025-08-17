import io
from unittest.mock import Mock, patch

import pytest

from webspark.http.request import Request
from webspark.utils.exceptions import HTTPException


def test_request_method():
    environ = {"REQUEST_METHOD": "POST"}
    request = Request(environ)
    assert request.method == "post"


def test_request_path():
    environ = {"PATH_INFO": "/test"}
    request = Request(environ)
    assert request.path == "/test"


def test_request_query_params():
    environ = {"QUERY_STRING": "a=1&b=2"}
    request = Request(environ)
    assert request.query_params == {"a": "1", "b": "2"}


def test_request_query_params_empty():
    environ = {"QUERY_STRING": ""}
    request = Request(environ)
    assert request.query_params == {}


def test_request_query_params_invalid():
    environ = {"QUERY_STRING": "a=1&b"}
    request = Request(environ)
    assert request.query_params == {"a": "1", "b": ""}


def test_request_headers():
    environ = {
        "HTTP_X_TEST": "test",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": "10",
    }
    request = Request(environ)
    assert request.headers == {
        "x-test": "test",
        "content-type": "application/json",
        "content-length": "10",
    }


def test_request_content_type():
    environ = {"CONTENT_TYPE": "application/json; charset=utf-8"}
    request = Request(environ)
    assert request.content_type == "application/json"


def test_request_content_length():
    environ = {"CONTENT_LENGTH": "10"}
    request = Request(environ)
    assert request.content_length == 10


def test_request_content_length_empty():
    environ = {}
    request = Request(environ)
    assert request.content_length == 0


def test_request_content_length_invalid():
    environ = {"CONTENT_LENGTH": "invalid"}
    request = Request(environ)
    assert request.content_length == 0


def test_request_charset():
    environ = {"CONTENT_TYPE": "application/json; charset=utf-8"}
    request = Request(environ)
    assert request.charset == "utf-8"


def test_request_charset_empty():
    environ = {"CONTENT_TYPE": "application/json"}
    request = Request(environ)
    assert request.charset == "utf-8"


def test_request_charset_multiple_params():
    environ = {"CONTENT_TYPE": "application/json; foo=bar; charset=utf-16"}
    request = Request(environ)
    assert request.charset == "utf-16"


def test_request_cookies():
    environ = {"HTTP_COOKIE": "a=1; b=2"}
    request = Request(environ)
    assert request.cookies == {"a": "1", "b": "2"}


def test_request_cookies_empty():
    environ = {}
    request = Request(environ)
    assert request.cookies == {}


def test_request_body_json():
    body = b'{"a": 1}'
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    request = Request(environ)
    assert request.body == {"a": 1}


def test_request_body_json_empty():
    body = b""
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    request = Request(environ)
    assert request.body == {}


def test_request_body_form_urlencoded():
    body = b"a=1&b=2"
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/x-www-form-urlencoded",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    request = Request(environ)
    assert request.body == {"a": "1", "b": "2"}


def test_request_body_multipart():
    body = (
        b'--boundary\r\nContent-Disposition: form-data; name="a"\r\n\r\n1\r\n'
        b"--boundary--\r\n"
    )
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    request = Request(environ)
    assert request.body == {"a": "1"}
    assert request.files == {}


def test_request_files_multipart():
    body = (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n"
        b"test content\r\n"
        b"--boundary--\r\n"
    )
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    request = Request(environ)
    assert request.files["file"]["filename"] == "test.txt"
    assert request.files["file"]["content_type"] == "text/plain"
    assert request.files["file"]["file"].read() == b"test content"


def test_request_files_not_multipart():
    environ = {"CONTENT_TYPE": "application/json"}
    request = Request(environ)
    assert request.files == {}


def test_request_body_method_not_allowed():
    environ = {"REQUEST_METHOD": "GET"}
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_body_too_large():
    environ = {"REQUEST_METHOD": "POST", "CONTENT_LENGTH": "10485761"}
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_body_missing_content_type():
    environ = {"REQUEST_METHOD": "POST", "CONTENT_LENGTH": "10"}
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_body_unsupported_content_type():
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/xml",
        "CONTENT_LENGTH": "10",
    }
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_body_invalid_json():
    body = b'{"a": 1'
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_path_params():
    request = Request({})
    params = {"a": "1"}
    request.path_params = params
    assert request.path_params == params


def test_request_view_instance():
    view_instance = Mock()
    environ = {"webspark.view_instance": view_instance}
    request = Request(environ)
    assert request.view_instance == view_instance


def test_request_webspark_instance():
    webspark_instance = Mock()
    environ = {"webspark.instance": webspark_instance}
    request = Request(environ)
    assert request.webspark == webspark_instance


@patch("webspark.http.request.MultipartParser._cleanup")
def test_request_del(mock_cleanup):
    body = (
        b"--boundary\r\n"
        b'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\n"
        b"test content\r\n"
        b"--boundary--\r\n"
    )
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "multipart/form-data; boundary=boundary",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
    }
    request = Request(environ)
    _ = request.files  # Access files to trigger parsing
    del request
    mock_cleanup.assert_called_once()
