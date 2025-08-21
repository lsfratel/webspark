import base64
import json
from datetime import datetime
from http.cookies import SimpleCookie

import pytest

from webspark.http.cookie import (
    _make_expires,
    _sign,
    _verify,
    parse_cookie,
    serialize_cookie,
)


def test_make_expires_with_datetime():
    dt = datetime(2023, 12, 25, 10, 30, 45)
    result = _make_expires(dt)
    assert result == "Mon, 25-Dec-2023 10:30:45 GMT"


def test_make_expires_with_int():
    result = _make_expires(3600)
    assert isinstance(result, str)
    assert "GMT" in result


def test_make_expires_with_invalid_type():
    with pytest.raises(ValueError, match="Date must be datetime or int"):
        _make_expires("invalid")


def test_sign_and_verify():
    data = "test_data"
    signature = _sign(data, "secret1")
    assert isinstance(signature, str)
    assert len(signature) > 0
    assert _verify(data, signature, ["secret1"]) is True


def test_verify_with_invalid_signature():
    assert _verify("test_data", "invalid_signature", ["secret1"]) is False


def test_verify_with_multiple_secrets():
    data = "test_data"
    signature = _sign(data, "secret2")
    assert _verify(data, signature, ["secret1", "secret2"]) is True


def test_serialize_without_secrets():
    data = {"key": "value", "number": 42}
    serialized = serialize_cookie("test_cookie", data)
    assert isinstance(serialized, str)
    assert "test_cookie" in serialized


def test_serialize_with_custom_options():
    data = {"key": "value"}
    serialized = serialize_cookie(
        "test_cookie",
        data,
        path="/test",
        max_age=1800,
        same_site="Strict",
        secure=True,
        http_only=False,
    )
    assert "Max-Age=1800" in serialized
    assert "Path=/test" in serialized
    assert "SameSite=Strict" in serialized
    assert "Secure" in serialized
    assert "HttpOnly" not in serialized


def test_serialize_with_expires_datetime():
    dt = datetime(2023, 12, 25, 10, 30, 45)
    serialized = serialize_cookie("test_cookie", {"key": "value"}, expires=dt)
    assert "expires=mon, 25-dec-2023 10:30:45 gmt" in serialized.lower()


def test_serialize_with_expires_int():
    serialized = serialize_cookie("test_cookie", {"key": "value"}, expires=3600)
    assert "expires=" in serialized.lower()


def test_serialize_with_secrets():
    data = {"key": "value"}
    serialized = serialize_cookie("test_cookie", data, secrets=["secret1"])
    assert "test_cookie" in serialized
    assert "." in serialized.split("test_cookie=")[1]


def test_parse_without_secrets():
    data = {"key": "value", "number": 42}
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = json.dumps(data)
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = parse_cookie(cookie_header)
    assert parsed["test_cookie"] == data


def test_parse_with_secrets():
    data = {"key": "value"}
    json_data = json.dumps(data)
    signature = _sign(json_data, "secret1")
    encoded_data = base64.urlsafe_b64encode(json_data.encode()).decode()
    signed_value = f"{encoded_data}.{signature}"

    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = signed_value
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = parse_cookie(cookie_header, secrets=["secret1"])
    assert parsed["test_cookie"] == data


def test_parse_with_invalid_json():
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = "invalid_json"
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = parse_cookie(cookie_header)
    assert parsed["test_cookie"] is None


def test_parse_with_invalid_signature():
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = "dGVzdF9kYXRh.invalid_signature"
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = parse_cookie(cookie_header, secrets=["secret1"])
    assert parsed["test_cookie"] is None


def test_parse_with_malformed_signed_cookie():
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = "dGVzdF9kYXRh"
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = parse_cookie(cookie_header, secrets=["secret1"])
    assert parsed["test_cookie"] is None


def test_parse_none_header():
    parsed = parse_cookie(None)
    assert parsed == {}


def test_parse_empty_header():
    parsed = parse_cookie("")
    assert parsed == {}


def test_serialize_with_multiple_secrets_random_choice():
    secrets = ["secret1", "secret2", "secret3"]
    data = {"key": "value"}

    serialized_cookies = []
    for _ in range(10):
        serialized_cookies.append(
            serialize_cookie("test_cookie", data, secrets=secrets)
        )

    for serialized in serialized_cookies:
        parsed = parse_cookie(serialized, secrets=secrets)
        assert parsed["test_cookie"] == data


def test_complex_data_serialization():
    complex_data = {
        "string": "value",
        "number": 42,
        "float": 3.14,
        "boolean": True,
        "list": [1, 2, 3],
        "nested": {"inner": "value"},
    }
    serialized = serialize_cookie("test_cookie", complex_data)
    parsed = parse_cookie(serialized)
    assert parsed["test_cookie"] == complex_data


def test_parse_signed_cookie_with_wrong_secret():
    data = {"key": "value"}
    serialized = serialize_cookie("test_cookie", data, secrets=["secret1"])

    parsed = parse_cookie(serialized, secrets=["different_secret"])
    assert parsed["test_cookie"] is None


def test_empty_data_serialization():
    serialized = serialize_cookie("test_cookie", {})
    assert "test_cookie" in serialized
    parsed = parse_cookie(serialized)
    assert parsed["test_cookie"] == {}


def test_none_data_serialization():
    serialized = serialize_cookie("test_cookie", None)
    assert "test_cookie" in serialized
    parsed = parse_cookie(serialized)
    assert parsed["test_cookie"] is None


def test_parse_with_valid_simple_cookie():
    data = {"user_id": 123, "username": "testuser"}
    serialized = serialize_cookie("test_cookie", data)
    parsed = parse_cookie(serialized)
    assert parsed["test_cookie"] == data


def test_parse_with_valid_signed_cookie():
    data = {"user_id": 123, "username": "testuser"}
    serialized = serialize_cookie("test_cookie", data, secrets=["my_secret"])
    parsed = parse_cookie(serialized, secrets=["my_secret"])
    assert parsed["test_cookie"] == data
