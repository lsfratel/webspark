import base64
import json
from datetime import datetime
from http.cookies import SimpleCookie

import pytest

from webspark.http.cookie import Cookie


def test_cookie_initialization():
    """Test cookie initialization with default options."""
    cookie = Cookie("test_cookie")
    assert cookie.name == "test_cookie"
    assert cookie.options["path"] == "/"
    assert cookie.options["max_age"] == 3600
    assert cookie.options["same_site"] == "Lax"
    assert cookie.options["secure"] is False
    assert cookie.options["http_only"] is True
    assert "secrets" not in cookie.options


def test_cookie_initialization_with_options():
    """Test cookie initialization with custom options."""
    options = {
        "path": "/api",
        "max_age": 7200,
        "same_site": "Strict",
        "secure": True,
        "http_only": False,
        "secrets": ["secret1", "secret2"],
    }
    cookie = Cookie("test_cookie", options)
    assert cookie.options["path"] == "/api"
    assert cookie.options["max_age"] == 7200
    assert cookie.options["same_site"] == "Strict"
    assert cookie.options["secure"] is True
    assert cookie.options["http_only"] is False
    assert cookie.options["secrets"] == ["secret1", "secret2"]


def test_cookie_initialization_with_empty_secrets():
    """Test cookie initialization with empty secrets list."""
    cookie = Cookie("test_cookie", {"secrets": []})
    assert "secrets" not in cookie.options


def test_make_expires_with_datetime():
    """Test _make_expires with datetime object."""
    dt = datetime(2023, 12, 25, 10, 30, 45)
    cookie = Cookie("test")
    result = cookie._make_expires(dt)
    assert result == "Mon, 25-Dec-2023 10:30:45 GMT"


def test_make_expires_with_int():
    """Test _make_expires with integer (seconds)."""
    cookie = Cookie("test")
    result = cookie._make_expires(3600)  # 1 hour
    # We can't assert the exact string since it depends on current time
    assert isinstance(result, str)
    assert "GMT" in result


def test_make_expires_with_invalid_type():
    """Test _make_expires with invalid type."""
    cookie = Cookie("test")
    with pytest.raises(ValueError, match="Date must be date or seconds"):
        cookie._make_expires("invalid")


def test_sign_and_verify():
    """Test signing and verification of cookie data."""
    cookie = Cookie("test", {"secrets": ["secret1"]})
    data = "test_data"
    signature = cookie._sign(data, "secret1")
    assert isinstance(signature, str)
    assert len(signature) > 0
    assert cookie._verify(data, signature) is True


def test_verify_with_invalid_signature():
    """Test verification with invalid signature."""
    cookie = Cookie("test", {"secrets": ["secret1"]})
    data = "test_data"
    assert cookie._verify(data, "invalid_signature") is False


def test_verify_with_multiple_secrets():
    """Test verification with multiple secrets."""
    cookie = Cookie("test", {"secrets": ["secret1", "secret2"]})
    data = "test_data"
    signature = cookie._sign(data, "secret2")
    assert cookie._verify(data, signature) is True


def test_serialize_without_secrets():
    """Test serialization without signing."""
    cookie = Cookie("test_cookie")
    data = {"key": "value", "number": 42}
    serialized = cookie.serialize(data)
    assert isinstance(serialized, str)
    assert "test_cookie" in serialized


def test_serialize_with_options():
    """Test serialization with custom options."""
    cookie = Cookie("test_cookie")
    data = {"key": "value"}
    serialized = cookie.serialize(data, {"max_age": 1800, "path": "/test"})
    assert "Max-Age=1800" in serialized
    assert "Path=/test" in serialized


def test_serialize_with_expires_datetime():
    """Test serialization with datetime expires."""
    cookie = Cookie("test_cookie")
    dt = datetime(2023, 12, 25, 10, 30, 45)
    serialized = cookie.serialize({"key": "value"}, {"expires": dt})
    # Cookie output uses lowercase "expires"
    assert "expires=mon, 25-dec-2023 10:30:45 gmt" in serialized.lower()


def test_serialize_with_expires_int():
    """Test serialization with integer expires."""
    cookie = Cookie("test_cookie")
    serialized = cookie.serialize({"key": "value"}, {"expires": 3600})
    assert "expires=" in serialized.lower()


def test_serialize_with_secrets():
    """Test serialization with signing."""
    cookie = Cookie("test_cookie", {"secrets": ["secret1"]})
    data = {"key": "value"}
    serialized = cookie.serialize(data)
    assert isinstance(serialized, str)
    assert "test_cookie" in serialized
    # Check that the value is signed (contains a dot)
    assert "." in serialized.split("test_cookie=")[1]


def test_parse_without_secrets():
    """Test parsing unsigned cookie."""
    cookie = Cookie("test_cookie")
    data = {"key": "value", "number": 42}

    # Create a proper cookie header using SimpleCookie
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = json.dumps(data)
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = cookie.parse(cookie_header)
    assert parsed == data


def test_parse_with_secrets():
    """Test parsing signed cookie."""
    cookie = Cookie("test_cookie", {"secrets": ["secret1"]})
    data = {"key": "value"}

    # Manually create a valid signed cookie for testing
    json_data = json.dumps(data)
    signature = cookie._sign(json_data, "secret1")
    encoded_data = base64.urlsafe_b64encode(json_data.encode()).decode()
    signed_value = f"{encoded_data}.{signature}"

    # Create proper cookie header
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = signed_value
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = cookie.parse(cookie_header)
    assert parsed == data


def test_parse_with_invalid_cookie_name():
    """Test parsing when cookie name doesn't match."""
    cookie = Cookie("test_cookie")
    # Create a cookie with a different name
    cookie_obj = SimpleCookie()
    cookie_obj["other_cookie"] = "value"
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = cookie.parse(cookie_header)
    assert parsed is None


def test_parse_with_invalid_json():
    """Test parsing with invalid JSON."""
    cookie = Cookie("test_cookie")
    # Create a cookie with invalid JSON
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = "invalid_json"
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = cookie.parse(cookie_header)
    assert parsed is None


def test_parse_with_invalid_signature():
    """Test parsing with invalid signature."""
    cookie = Cookie("test_cookie", {"secrets": ["secret1"]})
    # Create a cookie with invalid signature
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = "dGVzdF9kYXRh.invalid_signature"
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = cookie.parse(cookie_header)
    assert parsed is None


def test_parse_with_malformed_signed_cookie():
    """Test parsing with malformed signed cookie."""
    cookie = Cookie("test_cookie", {"secrets": ["secret1"]})
    # Create a cookie with missing signature part
    cookie_obj = SimpleCookie()
    cookie_obj["test_cookie"] = "dGVzdF9kYXRh"
    cookie_header = cookie_obj.output(header="", sep="").strip()

    parsed = cookie.parse(cookie_header)
    assert parsed is None


def test_parse_none_header():
    """Test parsing with None header."""
    cookie = Cookie("test_cookie")
    parsed = cookie.parse(None)
    assert parsed is None


def test_parse_empty_header():
    """Test parsing with empty header."""
    cookie = Cookie("test_cookie")
    parsed = cookie.parse("")
    assert parsed is None


def test_serialize_with_multiple_secrets_random_choice():
    """Test that serialization uses random secret from list."""
    secrets = ["secret1", "secret2", "secret3"]
    cookie = Cookie("test_cookie", {"secrets": secrets})
    data = {"key": "value"}

    # Collect serialized cookies
    serialized_cookies = []
    for _ in range(10):
        serialized = cookie.serialize(data)
        serialized_cookies.append(serialized)

    # Check that we got some cookies
    assert len(serialized_cookies) > 0

    # Parse each one back to verify it works
    for serialized in serialized_cookies:
        parsed = cookie.parse(serialized)
        assert parsed == data


def test_cookie_options_override():
    """Test that options can be overridden in serialize method."""
    cookie = Cookie("test_cookie", {"max_age": 3600, "path": "/"})
    data = {"key": "value"}
    serialized = cookie.serialize(data, {"max_age": 7200, "secure": True})

    # Check that override worked
    assert "Max-Age=7200" in serialized
    assert "Secure" in serialized
    # Original options should be preserved if not overridden
    assert "HttpOnly" in serialized


def test_complex_data_serialization():
    """Test serialization of complex data structures."""
    cookie = Cookie("test_cookie")
    complex_data = {
        "string": "value",
        "number": 42,
        "float": 3.14,
        "boolean": True,
        "list": [1, 2, 3],
        "nested": {"inner": "value"},
    }
    serialized = cookie.serialize(complex_data)
    assert isinstance(serialized, str)

    # Parse it back
    parsed = cookie.parse(serialized)
    assert parsed == complex_data


def test_parse_signed_cookie_with_wrong_secret():
    """Test parsing signed cookie with wrong secret."""
    # Create cookie with one set of secrets
    cookie1 = Cookie("test_cookie", {"secrets": ["secret1"]})
    data = {"key": "value"}
    serialized = cookie1.serialize(data)

    # Try to parse with different secrets
    cookie2 = Cookie("test_cookie", {"secrets": ["different_secret"]})

    # Extract just the cookie header part (remove "Set-Cookie: " prefix)
    if serialized.startswith("Set-Cookie: "):
        cookie_header = serialized[12:]  # Remove "Set-Cookie: " prefix
    else:
        cookie_header = serialized

    parsed = cookie2.parse(cookie_header)
    assert parsed is None


def test_empty_data_serialization():
    """Test serialization of empty data."""
    cookie = Cookie("test_cookie")
    serialized = cookie.serialize({})
    assert isinstance(serialized, str)
    assert "test_cookie" in serialized


def test_none_data_serialization():
    """Test serialization of None data."""
    cookie = Cookie("test_cookie")
    serialized = cookie.serialize(None)
    assert isinstance(serialized, str)
    assert "test_cookie" in serialized


def test_parse_with_valid_simple_cookie():
    """Test parsing a valid simple cookie created by Cookie class."""
    cookie = Cookie("test_cookie")
    data = {"user_id": 123, "username": "testuser"}
    serialized = cookie.serialize(data)

    # Parse it back
    parsed = cookie.parse(serialized)
    assert parsed == data


def test_parse_with_valid_signed_cookie():
    """Test parsing a valid signed cookie created by Cookie class."""
    cookie = Cookie("test_cookie", {"secrets": ["my_secret"]})
    data = {"user_id": 123, "username": "testuser"}
    serialized = cookie.serialize(data)

    # Parse it back
    parsed = cookie.parse(serialized)
    assert parsed == data
