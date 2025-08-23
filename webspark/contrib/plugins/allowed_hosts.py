from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...http import Context

from ...core.plugin import Plugin
from ...utils import HTTPException


class AllowedHostsPlugin(Plugin):
    """A plugin to validate the request's Host header against a list of allowed hosts."""

    def __init__(self, allowed_hosts: list[str]):
        self.allowed_hosts = allowed_hosts

    def apply(self, handler: Callable) -> Callable:
        """Apply the plugin to a view handler.

        Args:
            handler: The view handler to wrap.

        Returns:
            The wrapped handler with host validation.
        """

        def wrapped_handler(ctx: Context):
            self.check_allowed_hosts(ctx)
            return handler(ctx)

        return wrapped_handler

    def check_allowed_hosts(self, ctx: Context):
        """Check if the request host is allowed based on configuration.

        Validates the incoming request's host header against the configured
        ALLOWED_HOSTS setting. Supports exact matches and subdomain patterns.

        Args:
            ctx (Context): The context of the request being processed.

        Raises:
            HTTPException: If the host header is missing, invalid, or not
                          in the allowed hosts list (status code 400).
        """
        allowed_hosts = self.allowed_hosts

        if not allowed_hosts:
            raise HTTPException("Host not allowed.", status_code=400)

        host = ctx.host.split(":")[0] if ctx.host else ""

        if not host:
            raise HTTPException("Invalid or missing host header.", status_code=400)

        if "*" in allowed_hosts:
            return

        for pattern in allowed_hosts:
            if pattern.startswith("."):
                if host.endswith(pattern) or host == pattern[1:]:
                    return
            elif host == pattern:
                return

        raise HTTPException("Host not allowed.", status_code=400)
