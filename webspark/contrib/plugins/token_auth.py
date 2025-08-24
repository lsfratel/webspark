from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from ...http import Context

from ...core import Plugin
from ...utils import HTTPException


class TokenAuthPlugin(Plugin):
    """
    A plugin for token-based authentication using either the Authorization
    header or a cookie.

    Example with header:
        Authorization: Token <token>

    Example with cookie:
        Cookie: auth_token=<token>

    Args:
        token_loader (Callable[[str], Any]): A function that takes a token
            string and returns a user object or `None` if the token is invalid.
        scheme (str, optional): The authentication scheme to expect in headers.
            Defaults to "Token".
        cookie_name (str | None, optional): If provided, the plugin will try to
            get the token from this cookie name instead of the Authorization
            header.
    """

    def __init__(
        self,
        token_loader: Callable[[str], Any],
        scheme: str = "Token",
        cookie_name: str = None,
    ):
        self.token_loader = token_loader
        self.scheme = scheme
        self.cookie_name = cookie_name

    def _extract_from_cookie(self, ctx: Context) -> str | None:
        """Extract authentication token from cookie if cookie_name is configured.

        Args:
            ctx: The request context containing cookies.

        Returns:
            The token string if found in cookies, None otherwise.
        """
        if self.cookie_name:
            return ctx.cookies.get(self.cookie_name)
        return None

    def _extract_from_header(self, ctx: Context) -> str:
        """Extract authentication token from Authorization header.

        Args:
            ctx: The request context containing headers.

        Returns:
            The token string extracted from the Authorization header.

        Raises:
            HTTPException: If Authorization header is missing or has invalid format.
        """
        auth_header = ctx.headers.get("authorization")
        if not auth_header:
            ctx.set_header("WWW-Authenticate", self.scheme)
            raise HTTPException(
                "Authentication credentials were not provided.",
                status_code=401,
            )

        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0] != self.scheme:
            ctx.set_header("WWW-Authenticate", self.scheme)
            raise HTTPException("Invalid authentication scheme.", status_code=401)

        return parts[1]

    def _get_token(self, ctx: Context) -> str:
        """Get authentication token from cookie or header.

        Tries to extract token from cookie first (if configured),
        then falls back to Authorization header.

        Args:
            ctx: The request context.

        Returns:
            The authentication token string.

        Raises:
            HTTPException: If token cannot be found in either location.
        """
        token = self._extract_from_cookie(ctx)
        if token is not None:
            return token
        return self._extract_from_header(ctx)

    def _authenticate(self, ctx: Context, token: str) -> None:
        """Authenticate user using the provided token.

        Uses the token_loader function to validate the token and retrieve user data.
        Sets the user in the context state if authentication succeeds.

        Args:
            ctx: The request context.
            token: The authentication token to validate.

        Raises:
            HTTPException: If token is invalid or user cannot be loaded.
        """
        user = self.token_loader(token)
        if user is None:
            ctx.set_header("WWW-Authenticate", self.scheme)
            raise HTTPException("Invalid token.", status_code=401)
        ctx.state["user"] = user

    def apply(self, handler: Callable) -> Callable:
        """Apply token authentication to a handler function.

        Creates a wrapper that extracts and validates the authentication token
        before calling the original handler.

        Args:
            handler: The handler function to wrap with authentication.

        Returns:
            The wrapped handler function with authentication applied.
        """
        @wraps(handler)
        def wrapped_handler(ctx: Context):
            token = self._get_token(ctx)
            self._authenticate(ctx, token)
            handler(ctx)

        return wrapped_handler
