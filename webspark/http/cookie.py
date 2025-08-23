import base64
import hashlib
import hmac
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any

from ..utils.json import deserialize_json, serialize_json


def _make_expires(date: datetime | int) -> str:
    """
    Convert a datetime or int to a cookie expires string format.

    Args:
        date: Either a datetime object or an int representing seconds from now

    Returns:
        A formatted string suitable for cookie expires attribute

    Raises:
        ValueError: If date is neither datetime nor int
    """
    if isinstance(date, datetime):
        return date.strftime("%a, %d-%b-%Y %H:%M:%S GMT")
    elif isinstance(date, int):
        return (datetime.now() + timedelta(seconds=date)).strftime(
            "%a, %d-%b-%Y %H:%M:%S GMT"
        )
    raise ValueError("Date must be datetime or int.")


def _sign(data: str, secret: str) -> str:
    """
    Create an HMAC signature for the given data using the provided secret.

    Args:
        data: The data to sign
        secret: The secret key to use for signing

    Returns:
        A base64-encoded signature string
    """
    signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).decode()


def _verify(data: str, signature: str, secret: str):
    """
    Verify an HMAC signature against a list of possible secrets.

    Args:
        data: The original data that was signed
        signature: The signature to verify
        secret: The secret key to use for verification

    Returns:
        True if the signature is valid for any of the secrets, False otherwise
    """
    expected_signature = _sign(data, secret)
    if hmac.compare_digest(expected_signature, signature):
        return True
    return False


def serialize_cookie(
    name: str,
    data: Any,
    *,
    path: str = "/",
    max_age: int = 3600,
    same_site: str = "Lax",
    secret: str = None,
    secure: bool = False,
    http_only: bool = True,
    expires: datetime | int = None,
) -> str:
    """
    Serialize data into a signed cookie string.

    Args:
        name: The cookie name
        data: The data to serialize (will be JSON-encoded)
        path: Cookie path attribute (default: "/")
        max_age: Cookie max-age in seconds (default: 3600)
        same_site: SameSite attribute (default: "Lax")
        secret: Secret key for signing (optional)
        secure: Whether to set Secure flag (default: False)
        http_only: Whether to set HttpOnly flag (default: True)
        expires: Expiration date as datetime or seconds from now (optional)

    Returns:
        A formatted cookie string ready for Set-Cookie header
    """
    serialized_data = serialize_json(data).decode("utf-8")

    if secret:
        signature = _sign(serialized_data, secret)
        serialized_data = base64.urlsafe_b64encode(serialized_data.encode()).decode()
        serialized_data = f"{serialized_data}.{signature}"
    else:
        serialized_data = base64.urlsafe_b64encode(serialized_data.encode()).decode()

    cookie = SimpleCookie()
    cookie[name] = serialized_data

    if expires:
        cookie[name]["Expires"] = _make_expires(expires)
    if max_age:
        cookie[name]["Max-Age"] = max_age
    if path:
        cookie[name]["Path"] = path
    if http_only:
        cookie[name]["HttpOnly"] = http_only
    if secure:
        cookie[name]["Secure"] = secure
    if same_site:
        cookie[name]["SameSite"] = same_site

    return cookie.output(header="", sep="").strip()


def parse_cookie(header: str, secret: str = None):
    """
    Parse cookies from a Cookie header string.

    Args:
        header: The Cookie header value to parse
        secret: Secret key for verifying signed cookies (optional)

    Returns:
        A dictionary mapping cookie names to their deserialized values.
        Invalid or tampered cookies will have None as their value.
    """
    cookie = SimpleCookie(header)
    parsed: dict[str, Any] = {}

    for name, morsel in cookie.items():
        value = morsel.value

        if "." in value:
            try:
                data, signature = value.rsplit(".", 1)
                data = base64.urlsafe_b64decode(data).decode()
                if _verify(data, signature, secret):
                    parsed[name] = deserialize_json(data)
                else:
                    parsed[name] = None
            except Exception:
                parsed[name] = None
        else:
            try:
                parsed[name] = deserialize_json(base64.urlsafe_b64decode(value))
            except Exception:
                parsed[name] = None

    return parsed
