from __future__ import annotations

import base64
import hashlib
import hmac
import random
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from typing import Any

from ..utils.json import deserialize_json, serialize_json


class Cookie:
    """HTTP Cookie handling with optional signing support.

    This class provides functionality for serializing and parsing HTTP cookies
    with optional cryptographic signing to prevent tampering. It supports both
    simple JSON serialization and signed cookies for secure data storage.

    Example:
        # Create a simple cookie
        cookie = Cookie("session_id")
        serialized = cookie.serialize({"user_id": 123})

        # Create a signed cookie
        cookie = Cookie("auth_token", {"secrets": ["secret_key"]})
        serialized = cookie.serialize({"user_id": 123, "role": "admin"})

        # Parse a cookie
        data = cookie.parse(serialized)

    Attributes:
        name (str): The name of the cookie.
        options (dict): Configuration options for the cookie.
    """

    def __init__(self, name: str, options: dict[str, Any] | None = None):
        """Initialize a Cookie handler.

        Args:
            name: The name of the cookie.
            options: Configuration options for the cookie. Available options:
                - path (str): Cookie path (default: "/")
                - max_age (int): Cookie max age in seconds (default: 3600)
                - same_site (str): SameSite policy (default: "Lax")
                - secrets (list): List of secret keys for signing (default: [])
                - secure (bool): Secure flag (default: False)
                - http_only (bool): HttpOnly flag (default: True)
        """
        self.name = name
        options = options or {}
        self.options = {
            "path": "/",
            "max_age": 3600,
            "same_site": "Lax",
            "secrets": [],
            "secure": False,
            "http_only": True,
            **options,
        }
        if "secrets" in self.options:
            if len(self.options["secrets"]) == 0:
                del self.options["secrets"]

    @staticmethod
    def _make_expires(date: datetime | int):
        """Convert datetime or seconds to HTTP cookie expiration format.

        Args:
            date: Either a datetime object or seconds from now.

        Returns:
            str: Formatted expiration date string.

        Raises:
            ValueError: If date is neither datetime nor int.
        """
        if isinstance(date, datetime):
            return date.strftime("%a, %d-%b-%Y %H:%M:%S GMT")
        elif isinstance(date, int):
            return (datetime.now() + timedelta(seconds=date)).strftime(
                "%a, %d-%b-%Y %H:%M:%S GMT"
            )
        else:
            raise ValueError("Date must be date or seconds")

    def _sign(self, data: str, secret: str):
        """Sign data using HMAC-SHA256.

        Args:
            data: The data to sign.
            secret: The secret key for signing.

        Returns:
            str: Base64-encoded signature.
        """
        signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature).decode()

    def _verify(self, data: str, signature: str):
        """Verify data signature against available secrets.

        Args:
            data: The data to verify.
            signature: The signature to check against.

        Returns:
            bool: True if signature is valid, False otherwise.
        """
        for secret in self.options["secrets"]:
            expected_signature = self._sign(data, secret)
            if hmac.compare_digest(expected_signature, signature):
                return True
        return False

    def serialize(self, data: Any, overrides: dict[str, Any] | None = None):
        """Serialize data into an HTTP cookie string.

        Args:
            data: The data to serialize into the cookie.
            overrides: Optional dictionary of options to override defaults.

        Returns:
            str: Serialized cookie string ready for HTTP headers.

        Example:
            cookie = Cookie("session")
            serialized = cookie.serialize({"user_id": 123})
        """
        options = {**self.options, **(overrides or {})}
        new_data = serialize_json(data).decode(
            "utf-8"
        )

        if "secrets" in options and len(options["secrets"]) > 0:
            signature = self._sign(new_data, random.choice(options["secrets"]))
            new_data = base64.urlsafe_b64encode(new_data.encode()).decode()
            new_data = f"{new_data}.{signature}"

        cookie = SimpleCookie()
        cookie[self.name] = new_data

        if options.get("expires"):
            cookie[self.name]["Expires"] = self._make_expires(options["expires"])
        if options.get("max_age"):
            cookie[self.name]["Max-Age"] = options["max_age"]
        if options.get("path"):
            cookie[self.name]["Path"] = options["path"]
        if options.get("http_only"):
            cookie[self.name]["HttpOnly"] = options["http_only"]
        if options.get("secure"):
            cookie[self.name]["Secure"] = options["secure"]
        if options.get("same_site"):
            cookie[self.name]["SameSite"] = options["same_site"]

        return cookie.output(header="", sep="").strip()

    def parse(self, header: str | None):
        """Parse a cookie header string and extract data.

        Args:
            header: The cookie header string to parse.

        Returns:
            Any: The deserialized data, or None if parsing fails or cookie not found.

        Example:
            cookie = Cookie("session")
            data = cookie.parse("session=session_data; Path=/; HttpOnly")
        """
        cookie = SimpleCookie(header)
        if self.name not in cookie:
            return None

        cookie_value = cookie[self.name].value

        if "secrets" not in self.options:
            try:
                return deserialize_json(cookie_value)
            except Exception:
                return None

        try:
            data, signature = cookie_value.rsplit(".", 1)
            data = base64.urlsafe_b64decode(data).decode()
            if not self._verify(data, signature):
                return None
            return deserialize_json(data)
        except Exception:
            return None
