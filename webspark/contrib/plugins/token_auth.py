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
    A plugin for token-based authentication using the Authorization header.

    Example:
        Authorization: Token <token>

    Args:
        token_loader (Callable[[str], Any]): A function that takes a token
            string and returns a user object or `None` if the token is invalid.
        scheme (str, optional): The authentication scheme to expect.
            Defaults to "Token".
    """

    def __init__(
        self,
        token_loader: Callable[[str], Any],
        scheme: str = "Token",
    ):
        self.token_loader = token_loader
        self.scheme = scheme

    def apply(self, handler: Callable) -> Callable:
        """
        Apply the plugin to a view handler, wrapping it with authentication logic.
        """

        @wraps(handler)
        def wrapped_handler(ctx: Context):
            auth_header = ctx.headers.get("authorization")

            if not auth_header:
                ctx.set_header("WWW-Authenticate", self.scheme)
                raise HTTPException(
                    "Authentication credentials were not provided.", status_code=401
                )

            parts = auth_header.split(" ", 1)
            if len(parts) != 2 or parts[0] != self.scheme:
                ctx.set_header("WWW-Authenticate", self.scheme)
                raise HTTPException("Invalid authentication scheme.", status_code=401)

            token = parts[1]
            user = self.token_loader(token)

            if user is None:
                ctx.set_header("WWW-Authenticate", self.scheme)
                raise HTTPException("Invalid token.", status_code=401)

            ctx.state["user"] = user
            return handler(ctx)

        return wrapped_handler
