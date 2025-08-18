import io
from unittest.mock import Mock, patch

import pytest

from webspark.http.request import Request
from webspark.utils.exceptions import HTTPException


class ApplicationMock:
    def __init__(self, config_dict=None):
        self.config = type("Config", (), config_dict or {})()


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
    app = ApplicationMock()
    environ = {"HTTP_COOKIE": "a=1; b=2", "webspark.instance": app}
    request = Request(environ)
    assert request.get_cookies() == {"a": 1, "b": 2}


def test_request_cookies_empty():
    environ = {}
    request = Request(environ)
    assert request.get_cookies() == {}


def test_request_body_json():
    body = b'{"a": 1}'
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "webspark.instance": ApplicationMock(),
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
        "webspark.instance": ApplicationMock(),
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
        "webspark.instance": ApplicationMock(),
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
        "webspark.instance": ApplicationMock(),
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
        "webspark.instance": ApplicationMock(),
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
    environ = {"REQUEST_METHOD": "GET", "webspark.instance": ApplicationMock()}
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_body_too_large():
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_LENGTH": "10485761",
        "webspark.instance": ApplicationMock(),
    }
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_body_missing_content_type():
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_LENGTH": "10",
        "webspark.instance": ApplicationMock(),
    }
    request = Request(environ)
    with pytest.raises(HTTPException):
        _ = request.body


def test_request_body_unsupported_content_type():
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/xml",
        "CONTENT_LENGTH": "10",
        "webspark.instance": ApplicationMock(),
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
        "webspark.instance": ApplicationMock(),
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
        "webspark.instance": ApplicationMock(),
    }
    request = Request(environ)
    _ = request.files
    del request
    mock_cleanup.assert_called_once()


def test_request_ip_no_proxy():
    app = ApplicationMock()
    environ = {"REMOTE_ADDR": "127.0.0.1", "webspark.instance": app}
    request = Request(environ)
    assert request.ip == "127.0.0.1"


def test_request_ip_with_trust_proxy_header():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1, 172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "10.0.0.1"


def test_request_ip_with_trust_proxy_real_ip_header():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_REAL_IP": "10.0.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "10.0.0.1"


def test_request_ip_with_trust_proxy_forwarded_and_real_ip_headers():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1",
        "HTTP_X_REAL_IP": "172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "10.0.0.1"


def test_request_ip_with_trust_proxy_count():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True, "TRUSTED_PROXY_COUNT": 1})
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1, 172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "172.16.0.1"


def test_request_ip_with_trust_proxy_count_exact():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True, "TRUSTED_PROXY_COUNT": 2})
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1, 172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "10.0.0.1"


def test_request_ip_with_trust_proxy_count_more_than_ips():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True, "TRUSTED_PROXY_COUNT": 3})
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1, 172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "10.0.0.1"


def test_request_ip_with_trust_proxy_list():
    app = ApplicationMock(
        config_dict={
            "TRUST_PROXY": True,
            "TRUSTED_PROXY_LIST": ["192.168.1.1", "172.16.0.1"],
        }
    )
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1, 172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "10.0.0.1"


def test_request_ip_with_trust_proxy_list_all_trusted():
    app = ApplicationMock(
        config_dict={
            "TRUST_PROXY": True,
            "TRUSTED_PROXY_LIST": ["192.168.1.1", "172.16.0.1", "10.0.0.1"],
        }
    )
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1, 172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "10.0.0.1"


def test_request_ip_with_trust_proxy_list_last_untrusted():
    app = ApplicationMock(
        config_dict={"TRUST_PROXY": True, "TRUSTED_PROXY_LIST": ["172.16.0.1"]}
    )
    environ = {
        "REMOTE_ADDR": "192.168.1.1",
        "HTTP_X_FORWARDED_FOR": "10.0.0.1, 172.16.0.1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.ip == "192.168.1.1"


def test_request_scheme_no_proxy():
    app = ApplicationMock()
    environ = {"wsgi.url_scheme": "http", "webspark.instance": app}
    request = Request(environ)
    assert request.scheme == "http"


def test_request_scheme_with_trust_proxy():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "wsgi.url_scheme": "http",
        "HTTP_X_FORWARDED_PROTO": "https",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.scheme == "https"


def test_request_scheme_with_trust_proxy_multiple_values():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "wsgi.url_scheme": "http",
        "HTTP_X_FORWARDED_PROTO": "https, http",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.scheme == "https"


def test_request_host_no_proxy():
    app = ApplicationMock()
    environ = {"HTTP_HOST": "test.com", "webspark.instance": app}
    request = Request(environ)
    assert request.host == "test.com"


def test_request_host_with_trust_proxy():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "HTTP_HOST": "proxy.com",
        "HTTP_X_FORWARDED_HOST": "real.com",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.host == "real.com"


def test_request_host_with_trust_proxy_multiple_values():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "HTTP_HOST": "proxy.com",
        "HTTP_X_FORWARDED_HOST": "real.com, another.com",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.host == "real.com"


def test_request_is_secure_with_proxy():
    app = ApplicationMock(config_dict={"TRUST_PROXY": True})
    environ = {
        "wsgi.url_scheme": "http",
        "HTTP_X_FORWARDED_PROTO": "https",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.is_secure is True


def test_request_max_body_size_default():
    app = ApplicationMock()
    environ = {"webspark.instance": app}
    request = Request(environ)
    assert request.max_body_size == 10 * 1024 * 1024


def test_request_max_body_size_configured():
    app = ApplicationMock(config_dict={"MAX_BODY_SIZE": 5 * 1024 * 1024})
    environ = {"webspark.instance": app}
    request = Request(environ)
    assert request.max_body_size == 5 * 1024 * 1024


def test_request_is_secure_true():
    app = ApplicationMock()
    environ = {"wsgi.url_scheme": "https", "webspark.instance": app}
    request = Request(environ)
    assert request.is_secure is True


def test_request_is_secure_false():
    app = ApplicationMock()
    environ = {"wsgi.url_scheme": "http", "webspark.instance": app}
    request = Request(environ)
    assert request.is_secure is False


def test_request_host_from_server_name():
    app = ApplicationMock()
    environ = {"SERVER_NAME": "localhost", "webspark.instance": app}
    request = Request(environ)
    assert request.host == "localhost"


def test_request_url():
    app = ApplicationMock()
    environ = {
        "wsgi.url_scheme": "http",
        "HTTP_HOST": "localhost:8000",
        "PATH_INFO": "/test",
        "QUERY_STRING": "a=1",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.url == "http://localhost:8000/test?a=1"


def test_request_url_no_host():
    app = ApplicationMock()
    environ = {"PATH_INFO": "/test", "webspark.instance": app}
    request = Request(environ)
    assert request.url == "/test"


def test_request_url_no_query_string():
    app = ApplicationMock()
    environ = {
        "wsgi.url_scheme": "https",
        "HTTP_HOST": "example.com",
        "PATH_INFO": "/path",
        "webspark.instance": app,
    }
    request = Request(environ)
    assert request.url == "https://example.com/path"


def test_request_accept():
    environ = {"HTTP_ACCEPT": "application/json"}
    request = Request(environ)
    assert request.accept == "application/json"


def test_request_user_agent():
    environ = {"HTTP_USER_AGENT": "test-agent"}
    request = Request(environ)
    assert request.user_agent == "test-agent"
